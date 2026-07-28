"""RoomFlow: control lights/outlets per room based on time of day, day type,
presence, physical buttons and motion/threshold triggers."""
from __future__ import annotations

import logging
from datetime import time as dt_time, timedelta
from pathlib import Path

from homeassistant.components import panel_custom
from homeassistant.components.frontend import async_remove_panel, add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
    async_call_later,
)
from homeassistant.helpers.storage import Store
from homeassistant.helpers.sun import get_astral_event_date
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    CONF_TIME_SENSOR,
    CONF_DAY_TYPE_SENSOR,
    CONF_DAY_TYPE_SENSOR_INVERTED,
    CONF_HOME_SENSOR,
    CONF_PERIOD_MAP,
    CONF_TIME_MODE,
    CONF_DAY_TYPE_MODE,
    CONF_HOME_MODE,
    CONF_SCHEDULE,
    CONF_WEEKEND_DAYS,
    CONF_PERSON_ENTITIES,
    CONF_TIME_SOURCES,
    CONF_SUN_EVENTS,
    CONF_ILLUMINANCE_SENSOR,
    CONF_ILLUMINANCE_THRESHOLDS,
    CONF_PERIOD_BOOLEANS,
    CONF_DEVICE_NAME,
    CONF_AREA_ID,
    CONDITION_TYPE_TIME,
    CONDITION_TYPE_SUN,
    CONDITION_TYPE_NUMERIC,
    CONDITION_TYPE_STATE,
    CONDITION_TYPE_DAY_TYPE,
    CONDITION_TYPE_HOME,
    DAY_TYPE_MODE_SENSOR,
    DAY_TYPE_MODE_WEEKDAY_SELECTION,
    HOME_MODE_SENSOR,
    HOME_MODE_PERSONS,
    WEEKDAY_KEYS,
    DEFAULT_WEEKEND_DAYS,
    DEFAULT_DEVICE_NAME,
    LEGACY_PERIOD_KEY_MAP,
    DEVICE_TYPE_LIGHT,
    DEVICE_TYPE_OUTLET,
    WEEKEND_STATES,
    HOME_STATES,
    DEFAULT_TRANSITIONS,
    SIGNAL_RECOMPUTE,
    infer_periods,
    infer_day_type_mode,
    infer_home_mode,
)
from .websocket_api import async_register_commands

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "binary_sensor"]

# The card lives inside this component (custom_components/roomflow/www/) so
# copying just this one folder is enough - no separate copy into config/www
# and no manual Lovelace resource registration.
_CARD_URL_PATH = "/roomflow_static"
_CARD_JS_URL = f"{_CARD_URL_PATH}/roomflow-card.js"


def _pick_behavior(
    behaviors: dict, active_condition_ids: list[str], day_type: str, home_state: str
) -> dict | None:
    """Pick the right variant for a device/period: room conditions (in
    priority order) > away > weekend > default. Returns None if nothing
    applies - including when "default" itself is switched off for this
    period, meaning "leave this device alone" (e.g. button/manual-only
    during the day, while away/night overrides still turn it off)."""
    for condition_id in active_condition_ids:
        condition_cfg = behaviors.get(condition_id)
        if condition_cfg and condition_cfg.get("enabled"):
            return condition_cfg
    away_cfg = behaviors.get("away")
    if away_cfg and away_cfg.get("enabled") and home_state == "away":
        return away_cfg
    weekend_cfg = behaviors.get("weekend")
    if weekend_cfg and weekend_cfg.get("enabled") and day_type == "weekend":
        return weekend_cfg
    default_cfg = behaviors.get("default")
    if default_cfg and default_cfg.get("enabled", True):
        return default_cfg
    return None


def _active_room_conditions(hass: HomeAssistant, room: dict) -> list[str]:
    """IDs of this room's custom conditions that are currently true, in
    priority order (list order = priority, top = highest)."""
    active = []
    for condition in room.get("custom_conditions", []):
        entity_id = condition.get("entity_id")
        expected = condition.get("state")
        if not entity_id or not expected:
            continue
        state = hass.states.get(entity_id)
        if state is not None and state.state == expected:
            active.append(condition["id"])
    return active


def _normalize_behaviors(raw: dict) -> dict:
    """Backward compatibility: older formats stored the behavior directly
    without a 'default' wrapper."""
    if not raw:
        return {}
    if "default" in raw or "weekend" in raw or "away" in raw:
        return raw
    return {"default": raw}


def _device_domain(device: dict) -> str:
    return "light" if device.get("type") == DEVICE_TYPE_LIGHT else "switch"


def _parse_hms(raw: str) -> dt_time:
    hour, minute, *rest = (int(part) for part in raw.split(":"))
    return dt_time(hour, minute, rest[0] if rest else 0)


def _weekday_key(now_date) -> str:
    return WEEKDAY_KEYS[now_date.weekday()]


def _sun_boundary(hass: HomeAssistant, event: str, offset_minutes: int) -> dt_time | None:
    """Today's local time-of-day for one solar event + offset. None if the
    event doesn't occur today (polar day/night) or isn't a real astral.sun
    attribute (e.g. stale/invalid data) - a condition using it simply fails
    to match rather than crashing the rest of the room."""
    try:
        event_dt = get_astral_event_date(hass, event, dt_util.now())
    except AttributeError:
        _LOGGER.warning("RoomFlow: unrecognized sun event '%s'", event)
        return None
    if event_dt is None:
        return None
    local_dt = dt_util.as_local(event_dt) + timedelta(minutes=offset_minutes)
    return local_dt.time()


def _clamp_time(value: dt_time, earliest: str | None, latest: str | None) -> dt_time:
    """Clamp a resolved sun boundary to never be earlier/later than a fixed
    time on any day (a condition's "earliest"/"latest" fields) - e.g.
    sunset, but never before 18:00 and never after 22:00. Blank/unset means
    no clamp on that side."""
    if earliest:
        floor = _parse_hms(earliest)
        if value < floor:
            value = floor
    if latest:
        ceiling = _parse_hms(latest)
        if value > ceiling:
            value = ceiling
    return value


def _condition_boundary(hass: HomeAssistant, condition: dict) -> dt_time | None:
    """The dt_time a time/sun condition compares 'now' against, or None if
    it can't currently be resolved (e.g. a sun event that doesn't occur
    today)."""
    if condition.get("type") == CONDITION_TYPE_TIME:
        value = condition.get("value")
        return _parse_hms(value) if value else None
    boundary = _sun_boundary(hass, condition.get("event") or "sunrise", condition.get("offset_minutes") or 0)
    if boundary is None:
        return None
    return _clamp_time(boundary, condition.get("earliest"), condition.get("latest"))


def _numeric_condition_ok(hass: HomeAssistant, condition: dict) -> bool:
    entity_id = condition.get("entity_id")
    if not entity_id:
        return False
    state = hass.states.get(entity_id)
    if state is None:
        return False
    operator = condition.get("operator", "above")
    raw_value = condition.get("value")
    if operator == "equals":
        return bool(raw_value) and state.state.lower() == str(raw_value).lower()
    try:
        current = float(state.state)
        threshold = float(raw_value)
    except (TypeError, ValueError):
        return False
    return current <= threshold if operator == "below" else current >= threshold


def _state_condition_ok(hass: HomeAssistant, condition: dict) -> bool:
    entity_id = condition.get("entity_id")
    expected = condition.get("value")
    if not entity_id or not expected:
        return False
    state = hass.states.get(entity_id)
    if state is None:
        return False
    matches = state.state.lower() == str(expected).lower()
    return matches if condition.get("operator", "is") == "is" else not matches


def _condition_ok(
    hass: HomeAssistant, condition: dict, now_time: dt_time, is_weekend: bool, home_state: str
) -> bool:
    """True if one condition currently holds. Unknown/malformed condition
    types fail closed (never match) rather than raising, so one bad entry
    can't take down the rest of the room's period resolution."""
    ctype = condition.get("type")
    if ctype in (CONDITION_TYPE_TIME, CONDITION_TYPE_SUN):
        boundary = _condition_boundary(hass, condition)
        if boundary is None:
            return False
        return now_time >= boundary if condition.get("operator") == "after" else now_time < boundary
    if ctype == CONDITION_TYPE_NUMERIC:
        return _numeric_condition_ok(hass, condition)
    if ctype == CONDITION_TYPE_STATE:
        return _state_condition_ok(hass, condition)
    if ctype == CONDITION_TYPE_DAY_TYPE:
        return (condition.get("value") == "weekend") == is_weekend
    if ctype == CONDITION_TYPE_HOME:
        return condition.get("value") == home_state
    return False


def _period_condition_groups_match(
    hass: HomeAssistant, groups: list[dict], now_time: dt_time, is_weekend: bool, home_state: str
) -> bool:
    """A period is active if ANY of its condition groups is fully true -
    OR across groups, AND within a group (see const.py's period docs). An
    empty group (no conditions configured yet) never matches, so a freshly
    added group can't accidentally make its period always active."""
    for group in groups:
        conditions = group.get("conditions") or []
        if conditions and all(_condition_ok(hass, c, now_time, is_weekend, home_state) for c in conditions):
            return True
    return False


def _migrate_period_keys(cfg: dict) -> dict:
    """One-time migration of period dict keys from the legacy Swedish
    identifiers to the canonical English ones. Safe to run on every load."""
    default_transitions = cfg.get("default_transitions")
    if default_transitions:
        for old, new in LEGACY_PERIOD_KEY_MAP.items():
            if old in default_transitions and new not in default_transitions:
                default_transitions[new] = default_transitions.pop(old)

    for room in cfg.get("rooms", []):
        for device in room.get("devices", []):
            behaviors = device.get("behaviors")
            if behaviors:
                for old, new in LEGACY_PERIOD_KEY_MAP.items():
                    if old in behaviors and new not in behaviors:
                        behaviors[new] = behaviors.pop(old)
            transitions = device.get("transitions")
            if transitions:
                for old, new in LEGACY_PERIOD_KEY_MAP.items():
                    if old in transitions and new not in transitions:
                        transitions[new] = transitions.pop(old)
    return cfg


# Every settings key any previous config-flow generation ever wrote to
# entry.data, now that all of it lives in the card-editable JSON config
# store instead. Copied over once per key so existing installs keep working
# unchanged after upgrading, with no user action required.
_MIGRATABLE_ENTRY_DATA_KEYS = [
    CONF_TIME_MODE,
    CONF_TIME_SOURCES,
    CONF_TIME_SENSOR,
    CONF_PERIOD_MAP,
    CONF_SCHEDULE,
    CONF_SUN_EVENTS,
    CONF_ILLUMINANCE_SENSOR,
    CONF_ILLUMINANCE_THRESHOLDS,
    CONF_PERIOD_BOOLEANS,
    CONF_DAY_TYPE_MODE,
    CONF_DAY_TYPE_SENSOR,
    CONF_WEEKEND_DAYS,
    CONF_HOME_MODE,
    CONF_HOME_SENSOR,
    CONF_PERSON_ENTITIES,
    CONF_DEVICE_NAME,
    CONF_AREA_ID,
]


def _migrate_entry_data_to_config(entry: ConfigEntry, config: dict) -> None:
    for key in _MIGRATABLE_ENTRY_DATA_KEYS:
        if key not in config and key in entry.data:
            config[key] = entry.data[key]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
    stored = await store.async_load()
    config = _migrate_period_keys(stored or {})
    _migrate_entry_data_to_config(entry, config)
    config.setdefault("rooms", [])
    config.setdefault("buttons", [])
    config.setdefault("default_transitions", dict(DEFAULT_TRANSITIONS))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["store"] = store
    hass.data[DOMAIN]["config"] = config
    hass.data[DOMAIN]["entry"] = entry
    hass.data[DOMAIN].setdefault("button_unsubs", [])
    hass.data[DOMAIN].setdefault("motion_unsubs", [])
    hass.data[DOMAIN].setdefault("motion_off_timers", {})
    hass.data[DOMAIN].setdefault("motion_active_state", {})
    hass.data[DOMAIN].setdefault("motion_manual_override", {})

    # Register websocket commands only once
    if not hass.data[DOMAIN].get("ws_registered"):
        async_register_commands(hass)
        hass.data[DOMAIN]["ws_registered"] = True

    # These three read hass.data[DOMAIN]["config"] fresh on every call rather
    # than closing over values captured once here, so edits saved from the
    # card's Settings tab take effect immediately - no reload needed, same
    # as how _apply_to_rooms already re-reads "default_transitions" below.

    def _get_period() -> str | None:
        cfg = hass.data[DOMAIN]["config"]
        periods = infer_periods(cfg)  # already priority-ordered (top = highest)
        is_weekend = _get_day_type() == "weekend"
        home_state = _get_home_state()
        now_time = dt_util.now().time()

        # First period (list order, top = highest) with a true condition
        # group wins - see _period_condition_groups_match/_condition_ok
        # above and const.py's period docs for the OR-of-AND-groups shape.
        for period in periods:
            if _period_condition_groups_match(
                hass, period.get("condition_groups", []), now_time, is_weekend, home_state
            ):
                return period["id"]
        return None

    def _get_day_type() -> str:
        cfg = hass.data[DOMAIN]["config"]
        day_type_mode = infer_day_type_mode(cfg)
        if day_type_mode == DAY_TYPE_MODE_WEEKDAY_SELECTION:
            weekend_days = cfg.get(CONF_WEEKEND_DAYS, DEFAULT_WEEKEND_DAYS)
            return "weekend" if _weekday_key(dt_util.now().date()) in weekend_days else "weekday"
        if day_type_mode == DAY_TYPE_MODE_SENSOR:
            day_type_sensor = cfg.get(CONF_DAY_TYPE_SENSOR)
            if day_type_sensor:
                state = hass.states.get(day_type_sensor)
                if state is not None:
                    value = state.state.lower()
                    if value in WEEKEND_STATES:
                        return "weekend"
                    if value in ("on", "off"):
                        # No universal polarity for a plain binary_sensor
                        # (unlike home/away's "on" = home convention): some
                        # report "on" for weekend, others (e.g. a "workday"
                        # sensor) report "on" for weekday.
                        inverted = cfg.get(CONF_DAY_TYPE_SENSOR_INVERTED, False)
                        is_weekend = (value == "off") if inverted else (value == "on")
                        return "weekend" if is_weekend else "weekday"
        return "weekday"

    def _get_home_state() -> str:
        cfg = hass.data[DOMAIN]["config"]
        home_mode = infer_home_mode(cfg)
        if home_mode == HOME_MODE_PERSONS:
            person_entities = cfg.get(CONF_PERSON_ENTITIES, [])
            if not person_entities:
                return "home"
            for person_entity in person_entities:
                state = hass.states.get(person_entity)
                if state is not None and state.state.lower() == "home":
                    return "home"
            return "away"
        if home_mode == HOME_MODE_SENSOR:
            home_sensor = cfg.get(CONF_HOME_SENSOR)
            if home_sensor:
                state = hass.states.get(home_sensor)
                if state is not None:
                    return "home" if state.state.lower() in HOME_STATES else "away"
        return "home"

    # Exposed so the sensor platform can reuse the exact same logic instead
    # of duplicating it
    hass.data[DOMAIN]["get_period_fn"] = _get_period
    hass.data[DOMAIN]["get_day_type_fn"] = _get_day_type
    hass.data[DOMAIN]["get_home_state_fn"] = _get_home_state

    async def _apply_device(device: dict, behavior: dict, transition: float | None) -> None:
        try:
            await _apply_behavior(hass, device, behavior, transition)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "RoomFlow: could not apply behavior to %s: %s",
                device.get("entity_id"),
                err,
            )

    async def _apply_single_device(
        device: dict,
        period: str,
        day_type: str,
        home_state: str,
        active_condition_ids: list[str],
        default_transitions: dict,
    ) -> None:
        raw_behaviors = device.get("behaviors", {}).get(period)
        if not raw_behaviors:
            return
        behaviors = _normalize_behaviors(raw_behaviors)
        behavior = _pick_behavior(behaviors, active_condition_ids, day_type, home_state)
        if not behavior:
            return

        device_transitions = device.get("transitions", {}) or {}
        transition = device_transitions.get(period)
        if transition is None:
            transition = default_transitions.get(period)

        await _apply_device(device, behavior, transition)

    async def _apply_to_rooms(
        rooms: list, forced_period: str | None = None, respect_motion_control: bool = False
    ) -> None:
        if forced_period is not None:
            period = forced_period
        else:
            period = _get_period()
            if period is None:
                _LOGGER.debug("RoomFlow: could not resolve current period, skipping")
                return

        day_type = _get_day_type()
        home_state = _get_home_state()
        cfg = hass.data[DOMAIN]["config"]
        default_transitions = cfg.get("default_transitions", {})

        for room in rooms:
            active_condition_ids = _active_room_conditions(hass, room)
            for device in room.get("devices", []):
                # Motion-enabled devices are exclusively controlled by the
                # motion subsystem during routine ambient reapplies (time/
                # day-type/home-state ticking) - otherwise every such tick
                # would force them back on regardless of actual motion.
                # Explicit triggers (Test now, apply_now/force_period
                # buttons) still touch everything, same as before.
                if respect_motion_control and device.get("motion", {}).get("enabled"):
                    continue
                await _apply_single_device(
                    device, period, day_type, home_state, active_condition_ids, default_transitions
                )

    async def apply_current_period() -> None:
        cfg = hass.data[DOMAIN]["config"]
        await _apply_to_rooms(cfg.get("rooms", []), respect_motion_control=True)

    async def apply_room(room_id: str) -> None:
        cfg = hass.data[DOMAIN]["config"]
        rooms = [r for r in cfg.get("rooms", []) if r.get("id") == room_id]
        await _apply_to_rooms(rooms)

    def _get_room(room_id: str) -> dict | None:
        cfg = hass.data[DOMAIN]["config"]
        return next((r for r in cfg.get("rooms", []) if r.get("id") == room_id), None)

    def _motion_key(room_id: str, entity_id: str) -> str:
        return f"{room_id}:{entity_id}"

    def _cancel_motion_timer(key: str) -> None:
        cancel = hass.data[DOMAIN]["motion_off_timers"].pop(key, None)
        if cancel:
            cancel()

    async def _turn_off_room(room: dict) -> None:
        for device in room.get("devices", []):
            key = _motion_key(room["id"], device["entity_id"])
            hass.data[DOMAIN]["motion_manual_override"][key] = True
            _cancel_motion_timer(key)
            try:
                await hass.services.async_call(
                    _device_domain(device), "turn_off", {"entity_id": device["entity_id"]}
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "RoomFlow: could not turn off %s: %s", device.get("entity_id"), err
                )

    async def _toggle_room(room: dict) -> None:
        devices = room.get("devices", [])
        if not devices:
            return
        on_count = 0
        for device in devices:
            state = hass.states.get(device["entity_id"])
            if state and state.state == "on":
                on_count += 1
        turn_on = on_count < (len(devices) / 2)
        service = "turn_on" if turn_on else "turn_off"
        for device in devices:
            key = _motion_key(room["id"], device["entity_id"])
            hass.data[DOMAIN]["motion_manual_override"][key] = True
            _cancel_motion_timer(key)
            try:
                await hass.services.async_call(
                    _device_domain(device), service, {"entity_id": device["entity_id"]}
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "RoomFlow: could not toggle %s: %s", device.get("entity_id"), err
                )

    hass.data[DOMAIN]["apply_fn"] = apply_current_period
    hass.data[DOMAIN]["apply_room_fn"] = apply_room

    # ---------- Physical buttons ----------

    async def _handle_button_press(button: dict, event: Event) -> None:
        old_state = event.data.get("old_state")
        if old_state is None:
            # Avoid triggering on HA restart / entity just appearing
            return
        room = _get_room(button.get("room_id"))
        if not room:
            return
        action = button.get("action")
        try:
            if action == "toggle":
                await _toggle_room(room)
            elif action == "off":
                await _turn_off_room(room)
            elif action == "apply_now":
                await apply_room(room["id"])
            elif action == "force_period":
                await _apply_to_rooms([room], forced_period=button.get("force_period"))
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "RoomFlow: error handling button press (%s): %s",
                button.get("entity_id"),
                err,
            )

    def _setup_button_listeners() -> None:
        for unsub in hass.data[DOMAIN].get("button_unsubs", []):
            unsub()
        unsubs = []
        buttons = hass.data[DOMAIN]["config"].get("buttons", [])
        for button in buttons:
            entity_id = button.get("entity_id")
            if not entity_id:
                continue

            def _make_handler(btn):
                async def _handler(event: Event) -> None:
                    await _handle_button_press(btn, event)

                return _handler

            unsubs.append(
                async_track_state_change_event(hass, [entity_id], _make_handler(button))
            )
        hass.data[DOMAIN]["button_unsubs"] = unsubs

    hass.data[DOMAIN]["refresh_buttons_fn"] = _setup_button_listeners
    _setup_button_listeners()

    # ---------- Motion / threshold triggers ----------

    def _is_trigger_active(trigger: dict) -> bool:
        entity_id = trigger.get("entity_id")
        if not entity_id:
            return False
        state = hass.states.get(entity_id)
        if state is None:
            return False
        ttype = trigger.get("type", "motion")
        if ttype == "motion":
            return state.state == "on"
        if ttype == "threshold_above":
            try:
                value = float(state.state)
            except (TypeError, ValueError):
                return False
            threshold = trigger.get("threshold", 100)
            return value > threshold
        return False

    def _is_room_active(room: dict) -> bool:
        triggers = room.get("motion", {}).get("triggers", [])
        return any(_is_trigger_active(t) for t in triggers)

    def _motion_devices(room: dict) -> list:
        return [d for d in room.get("devices", []) if d.get("motion", {}).get("enabled")]

    async def _turn_off_device(device: dict) -> None:
        try:
            await hass.services.async_call(
                _device_domain(device), "turn_off", {"entity_id": device["entity_id"]}
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "RoomFlow: could not turn off %s: %s", device.get("entity_id"), err
            )

    async def _dim_device_for_warning(device: dict, brightness: float) -> None:
        if _device_domain(device) != "light":
            return  # the dim-warning stage only makes sense for lights
        try:
            await hass.services.async_call(
                "light", "turn_on", {"entity_id": device["entity_id"], "brightness": brightness}
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "RoomFlow: could not dim %s for motion warning: %s", device.get("entity_id"), err
            )

    async def _apply_motion_device_on(room: dict, device: dict) -> None:
        period = _get_period()
        if period is None:
            return
        day_type = _get_day_type()
        home_state = _get_home_state()
        active_condition_ids = _active_room_conditions(hass, room)
        cfg = hass.data[DOMAIN]["config"]
        default_transitions = cfg.get("default_transitions", {})
        await _apply_single_device(
            device, period, day_type, home_state, active_condition_ids, default_transitions
        )

    def _schedule_motion_off(room_id: str, device: dict, motion_cfg: dict) -> None:
        entity_id = device["entity_id"]
        key = _motion_key(room_id, entity_id)
        device_motion_cfg = device.get("motion", {})
        off_delay = device_motion_cfg.get("off_delay_minutes")
        if off_delay is None:
            off_delay = motion_cfg.get("timeout_minutes", 10)
        warn_enabled = motion_cfg.get("warn_enabled", False)
        warn_minutes = motion_cfg.get("warn_minutes", 3)
        warn_brightness = motion_cfg.get("warn_brightness", 25)

        async def _after_warn(_now) -> None:
            hass.data[DOMAIN]["motion_off_timers"].pop(key, None)
            final_room = _get_room(room_id)
            if not final_room:
                return
            final_device = next(
                (d for d in final_room.get("devices", []) if d["entity_id"] == entity_id), None
            )
            if final_device:
                await _turn_off_device(final_device)

        async def _after_off_delay(_now) -> None:
            hass.data[DOMAIN]["motion_off_timers"].pop(key, None)
            current_room = _get_room(room_id)
            if not current_room:
                return
            current_device = next(
                (d for d in current_room.get("devices", []) if d["entity_id"] == entity_id), None
            )
            if not current_device:
                return
            if warn_enabled:
                await _dim_device_for_warning(current_device, warn_brightness)
                cancel = async_call_later(hass, warn_minutes * 60, _after_warn)
                hass.data[DOMAIN]["motion_off_timers"][key] = cancel
            else:
                await _turn_off_device(current_device)

        _cancel_motion_timer(key)
        cancel = async_call_later(hass, off_delay * 60, _after_off_delay)
        hass.data[DOMAIN]["motion_off_timers"][key] = cancel

    async def _handle_motion_change(room_id: str, event: Event) -> None:
        room = _get_room(room_id)
        if not room:
            return
        motion_cfg = room.get("motion", {})
        if not motion_cfg.get("enabled"):
            return

        new_active = _is_room_active(room)
        previous_active = hass.data[DOMAIN]["motion_active_state"].get(room_id, False)
        if new_active == previous_active:
            return
        hass.data[DOMAIN]["motion_active_state"][room_id] = new_active

        motion_devices = _motion_devices(room)

        if new_active:
            for device in motion_devices:
                key = _motion_key(room_id, device["entity_id"])
                # A fresh motion cycle always releases any manual-mode lock
                # from a prior button press, per RoomFlow's design.
                hass.data[DOMAIN]["motion_manual_override"].pop(key, None)
                _cancel_motion_timer(key)
                await _apply_motion_device_on(room, device)
        else:
            for device in motion_devices:
                key = _motion_key(room_id, device["entity_id"])
                if hass.data[DOMAIN]["motion_manual_override"].get(key):
                    continue
                _schedule_motion_off(room_id, device, motion_cfg)

    def _setup_motion_listeners() -> None:
        for unsub in hass.data[DOMAIN].get("motion_unsubs", []):
            unsub()
        for cancel in hass.data[DOMAIN].get("motion_off_timers", {}).values():
            cancel()
        hass.data[DOMAIN]["motion_off_timers"] = {}
        hass.data[DOMAIN]["motion_active_state"] = {}
        hass.data[DOMAIN]["motion_manual_override"] = {}

        unsubs = []
        rooms = hass.data[DOMAIN]["config"].get("rooms", [])
        for room in rooms:
            motion_cfg = room.get("motion", {})
            if not motion_cfg.get("enabled"):
                continue
            triggers = motion_cfg.get("triggers", [])
            entity_ids = [t.get("entity_id") for t in triggers if t.get("entity_id")]
            if not entity_ids:
                continue

            hass.data[DOMAIN]["motion_active_state"][room["id"]] = _is_room_active(room)

            def _make_handler(room_id):
                async def _handler(event: Event) -> None:
                    await _handle_motion_change(room_id, event)

                return _handler

            unsubs.append(
                async_track_state_change_event(hass, entity_ids, _make_handler(room["id"]))
            )
        hass.data[DOMAIN]["motion_unsubs"] = unsubs

    hass.data[DOMAIN]["refresh_motion_fn"] = _setup_motion_listeners
    _setup_motion_listeners()

    # ---------- Time / day-type / home listeners ----------
    #
    # Whatever combination of "existing entity" vs "built-in" modes is
    # active, every trigger source funnels through the same callback: apply
    # the current period to the rooms, then tell the sensor platform (which
    # has no entity of its own to watch in built-in modes) to recompute too.

    async def _handle_relevant_change(*_args) -> None:
        await apply_current_period()
        async_dispatcher_send(hass, SIGNAL_RECOMPUTE)

    def _setup_time_listeners() -> None:
        for unsub in hass.data[DOMAIN].get("time_unsubs", []):
            unsub()

        cfg = hass.data[DOMAIN]["config"]
        periods = infer_periods(cfg)
        day_type_mode = infer_day_type_mode(cfg)
        home_mode = infer_home_mode(cfg)
        day_type_sensor = cfg.get(CONF_DAY_TYPE_SENSOR)
        home_sensor = cfg.get(CONF_HOME_SENSOR)
        person_entities = cfg.get(CONF_PERSON_ENTITIES, [])

        unsubs: list = []

        tracked_entities: list[str] = []
        time_boundary_values: set[str] = set()
        has_sun_condition = False
        for period in periods:
            for group in period.get("condition_groups", []):
                for condition in group.get("conditions", []):
                    ctype = condition.get("type")
                    if ctype in (CONDITION_TYPE_NUMERIC, CONDITION_TYPE_STATE):
                        entity_id = condition.get("entity_id")
                        if entity_id:
                            tracked_entities.append(entity_id)
                    elif ctype == CONDITION_TYPE_TIME:
                        value = condition.get("value")
                        if value:
                            time_boundary_values.add(value)
                    elif ctype == CONDITION_TYPE_SUN:
                        has_sun_condition = True

        if day_type_mode == DAY_TYPE_MODE_SENSOR and day_type_sensor:
            tracked_entities.append(day_type_sensor)
        if home_mode == HOME_MODE_SENSOR and home_sensor:
            tracked_entities.append(home_sensor)
        if home_mode == HOME_MODE_PERSONS:
            tracked_entities.extend(person_entities)
        for room in cfg.get("rooms", []):
            for condition in room.get("custom_conditions", []):
                entity_id = condition.get("entity_id")
                if entity_id:
                    tracked_entities.append(entity_id)

        if tracked_entities:
            unsubs.append(
                async_track_state_change_event(hass, tracked_entities, _handle_relevant_change)
            )

        for time_str in time_boundary_values:
            boundary = _parse_hms(time_str)
            unsubs.append(
                async_track_time_change(
                    hass,
                    _handle_relevant_change,
                    hour=boundary.hour,
                    minute=boundary.minute,
                    second=boundary.second,
                )
            )

        if has_sun_condition:
            # Solar event times shift by a minute or two each day, so exact
            # per-boundary scheduling would need dynamic rescheduling. A
            # coarse 1-minute poll is far simpler and the resulting lag is
            # negligible.
            unsubs.append(
                async_track_time_interval(hass, _handle_relevant_change, timedelta(minutes=1))
            )

        if day_type_mode == DAY_TYPE_MODE_WEEKDAY_SELECTION:
            unsubs.append(
                async_track_time_change(hass, _handle_relevant_change, hour=0, minute=0, second=0)
            )

        hass.data[DOMAIN]["time_unsubs"] = unsubs

    hass.data[DOMAIN]["refresh_time_fn"] = _setup_time_listeners
    _setup_time_listeners()

    def _refresh_device_registration() -> None:
        cfg = hass.data[DOMAIN]["config"]
        device_registry = dr.async_get(hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, entry.entry_id)})
        if device:
            device_registry.async_update_device(
                device.id,
                area_id=cfg.get(CONF_AREA_ID),
                name=cfg.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME),
            )

    hass.data[DOMAIN]["refresh_device_fn"] = _refresh_device_registration

    # Apply immediately on start/reload so the current state takes effect
    await apply_current_period()

    # Serve the card straight from this component's own www/ folder and
    # auto-register it as a Lovelace resource, so installing/copying just
    # this one folder is enough for both the sidebar page and any dashboard
    # card - no manual config/www copy or Resources entry needed.
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_CARD_URL_PATH, str(Path(__file__).parent / "www"), cache_headers=False)]
        )
    except (RuntimeError, ValueError):
        # Already registered (e.g. on entry reload)
        pass
    add_extra_js_url(hass, _CARD_JS_URL)

    # Register a dedicated sidebar page (reuses the same card as a full page)
    try:
        await panel_custom.async_register_panel(
            hass,
            webcomponent_name="roomflow-card",
            frontend_url_path="roomflow",
            sidebar_title="RoomFlow",
            sidebar_icon="mdi:home-lightning-bolt-outline",
            module_url=_CARD_JS_URL,
            embed_iframe=False,
            require_admin=False,
            config={},
        )
    except ValueError:
        # Already registered (e.g. on entry reload)
        pass

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # The device is created by the sensor/binary_sensor platforms above via
    # their DeviceInfo, so only now does it exist to update.
    _refresh_device_registration()

    return True


async def _apply_behavior(
    hass: HomeAssistant, device: dict, behavior: dict, transition: float | None
) -> None:
    entity_id = device["entity_id"]
    device_type = device.get("type", DEVICE_TYPE_LIGHT)
    state = behavior.get("state", "off")

    if device_type == DEVICE_TYPE_LIGHT:
        service_data: dict = {"entity_id": entity_id}
        if transition is not None:
            service_data["transition"] = transition

        if state == "on":
            if "brightness" in behavior:
                service_data["brightness"] = behavior["brightness"]
            if "color_temp_kelvin" in behavior:
                service_data["color_temp_kelvin"] = behavior["color_temp_kelvin"]
            await hass.services.async_call("light", "turn_on", service_data)
        else:
            await hass.services.async_call("light", "turn_off", service_data)
    elif device_type == DEVICE_TYPE_OUTLET:
        service = "turn_on" if state == "on" else "turn_off"
        await hass.services.async_call("switch", service, {"entity_id": entity_id})


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    for unsub in hass.data[DOMAIN].get("time_unsubs", []):
        unsub()
    for button_unsub in hass.data[DOMAIN].get("button_unsubs", []):
        button_unsub()
    for motion_unsub in hass.data[DOMAIN].get("motion_unsubs", []):
        motion_unsub()
    for cancel in hass.data[DOMAIN].get("motion_off_timers", {}).values():
        cancel()
    try:
        async_remove_panel(hass, "roomflow")
    except ValueError:
        pass
    hass.data.pop(DOMAIN, None)
    return True
