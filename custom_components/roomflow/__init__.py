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
from homeassistant.helpers import area_registry as ar, device_registry as dr
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
    VERSION,
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
    EVENT_DEVICE_PROFILES,
    TIMED_CLICK_TYPES,
    CLICK_TYPE_SHORT_TIMED,
    CLICK_TYPE_LONG_TIMED,
    DEFAULT_LONG_PRESS_MS,
    CLICK_TYPE_HOLD,
    HOLD_DIM_STEP,
    HOLD_DIM_INTERVAL_SECONDS,
    STALE_EVENT_MAX_AGE_SECONDS,
    WEEKEND_STATES,
    HOME_STATES,
    DEFAULT_TRANSITIONS,
    DEFAULT_SCHEDULE_ID,
    SIGNAL_RECOMPUTE,
    infer_schedules,
    periods_for_schedule,
    transitions_for_schedule,
    infer_day_type_mode,
    infer_home_mode,
)
from .logs import async_load_logs, log_button_press, log_device_change, log_period_change
# websocket_api is imported lazily inside async_setup_entry (below), not
# here at module level - it now imports condition-cascade helpers back
# from this module (_active_room_conditions and friends), which aren't
# defined yet this early in the file; importing it only once this module
# has finished executing avoids a circular-import error at startup.

_LOGGER = logging.getLogger(__name__)

# _resolve_status_text's three fixed (non-user-named) outcomes, as
# sentinels rather than literal English words - it has no access to the
# viewer's language, unlike the frontend (see detectLang/STRINGS in
# roomflow-card.js). Two different audiences read its return value:
# sensor.py resolves these back to the stable English words below for the
# actual House/Floor/Room status sensors' native_value (state text should
# stay a stable, machine-parseable value - not vary with a browser's
# language, and not something an automation matching on it would need to
# track); the Overview tab (ws_get_dashboard) instead sends the sentinel
# straight through, and the card translates it itself (see
# _displayStatusText) the same way it already does for period/condition
# names.
STATUS_SENTINEL_ACTIVE = "__status_active__"
STATUS_SENTINEL_AWAY = "__status_away__"
STATUS_SENTINEL_WEEKEND = "__status_weekend__"
STATUS_SENTINEL_TEXT = {
    STATUS_SENTINEL_ACTIVE: "Active",
    STATUS_SENTINEL_AWAY: "Away",
    STATUS_SENTINEL_WEEKEND: "Weekend",
}

PLATFORMS: list[str] = ["sensor", "binary_sensor"]

# The card lives inside this component (custom_components/roomflow/www/) so
# copying just this one folder is enough - no separate copy into config/www
# and no manual Lovelace resource registration.
_CARD_URL_PATH = "/roomflow_static"
# ?v=<version> busts the browser's own cache of the module on every release -
# StaticPathConfig's cache_headers=False below only controls what the HA
# server sends, it doesn't stop a browser (or its ES-module cache) from
# reusing a previously-fetched copy of this exact URL for the rest of the
# tab's session, which otherwise silently runs stale card JS against a
# newer backend until the user manually hard-refreshes.
_CARD_JS_URL = f"{_CARD_URL_PATH}/roomflow-card.js?v={VERSION}"


def _pick_manual_on_behavior(
    behaviors: dict,
    active_condition_ids: list[str],
    day_type: str,
    home_state: str,
    away_default: dict | None = None,
) -> dict | None:
    """Same tier order `_pick_behavior` uses (condition > away > weekend >
    default) for a manual "turn on" button press specifically - except an
    off-resolving tier never gets to veto it. A condition/away override
    that's only there to force things off automatically (e.g. a "Natt"
    condition bound to a global night switch) shouldn't also block a
    deliberate manual on for as long as that condition happens to stay
    active - only a tier that itself wants "on" can supply the press's
    target; anything that resolves "off" (or isn't enabled/active for
    this period) is skipped in favour of the next tier. Falls through to
    the period's own default as the final answer either way, even if
    that's "off" too - a device with no configured "on" value anywhere
    for this period genuinely has none to give."""
    for condition_id in active_condition_ids:
        condition_cfg = behaviors.get(condition_id)
        if condition_cfg and condition_cfg.get("enabled") and condition_cfg.get("state") == "on":
            return condition_cfg
    away_cfg = behaviors.get("away")
    if away_cfg and away_cfg.get("enabled") and home_state == "away" and away_cfg.get("state") == "on":
        return away_cfg
    if away_default and away_default.get("enabled") and home_state == "away" and away_default.get("state") == "on":
        return away_default
    weekend_cfg = behaviors.get("weekend")
    if weekend_cfg and weekend_cfg.get("enabled") and day_type == "weekend" and weekend_cfg.get("state") == "on":
        return weekend_cfg
    return behaviors.get("default")


def _pick_behavior(
    behaviors: dict,
    active_condition_ids: list[str],
    day_type: str,
    home_state: str,
    default_enabled: bool = True,
    away_default: dict | None = None,
) -> dict | None:
    """Pick the right variant for a device/period: room conditions (in
    priority order) > this period's own away override > the device-wide
    away default (used only when the period has no away override of its
    own) > weekend > default. Returns None if nothing applies - including
    when the period's control mode isn't "schedule" (`default_enabled`
    False), meaning "leave this device alone" here, while away/weekend/
    condition overrides still act if enabled."""
    for condition_id in active_condition_ids:
        condition_cfg = behaviors.get(condition_id)
        if condition_cfg and condition_cfg.get("enabled"):
            return condition_cfg
    away_cfg = behaviors.get("away")
    if away_cfg and away_cfg.get("enabled") and home_state == "away":
        return away_cfg
    if away_default and away_default.get("enabled") and home_state == "away":
        return away_default
    weekend_cfg = behaviors.get("weekend")
    if weekend_cfg and weekend_cfg.get("enabled") and day_type == "weekend":
        return weekend_cfg
    default_cfg = behaviors.get("default")
    if default_cfg and default_enabled:
        return default_cfg
    return None


def _control_mode(device: dict, period: str) -> dict:
    """Per-period control mode for a device: which mechanism is allowed to
    act on it this period - "schedule" (ambient time/day-type/home-state
    ticks), "motion" (only the motion-sensor definition referenced by
    motion_sensor_id, optionally split into separate on/off reactions via
    motion_on/motion_off), or "button" (left alone by both; only touched
    by an explicit bound button/Test-now/force_period call). Falls back to
    inferring from the pre-control-mode fields (device-wide motion.enabled,
    per-period behaviors.default.enabled) for configs the card hasn't
    resaved with an explicit "control" block yet - such configs have no
    definition to reference, so motion_sensor_id is None until the device
    is re-pointed at one in the card."""
    control = (device.get("control") or {}).get(period)
    if control:
        return {
            "mode": control.get("mode", "schedule"),
            "motion_sensor_id": control.get("motion_sensor_id"),
            "motion_on": control.get("motion_on", True),
            "motion_off": control.get("motion_off", True),
        }
    if device.get("motion", {}).get("enabled"):
        return {"mode": "motion", "motion_sensor_id": None, "motion_on": True, "motion_off": True}
    default_cfg = _normalize_behaviors(device.get("behaviors", {}).get(period)).get("default")
    if default_cfg and default_cfg.get("enabled", True) is False:
        return {"mode": "button", "motion_sensor_id": None, "motion_on": True, "motion_off": True}
    return {"mode": "schedule", "motion_sensor_id": None, "motion_on": True, "motion_off": True}


def _behavior_signature(behavior: dict) -> tuple:
    """A comparable snapshot of what a behavior asks for, used to tell
    "the schedule's target actually changed" apart from "we're just being
    asked to re-apply the same thing again" (ambient ticks re-resolve and
    re-apply on every trigger, not only when something differs). Two
    resolved behaviors that ask for the same practical outcome compare
    equal even if a different tier (condition/away/weekend/default)
    produced them."""
    if behavior.get("state") != "on":
        return ("off",)
    return ("on", behavior.get("brightness"), behavior.get("color_temp_kelvin"))


def _click_type_value_matches(click_type: str | None, *candidates: str | None) -> bool:
    """True if a button-trigger's click_type ("single"/"double"/"long", or
    "any"/unset to always match) is a case-insensitive substring of any of
    the given candidate strings. Shared by both button-trigger mechanisms
    (entity state-change and raw HA bus event) so "single" matching a
    derived "single_press" value means the same thing either way -
    integrations/devices don't agree on exact vocabulary, so a substring
    match covers more real-world button hardware than an exact comparison
    would."""
    click_type = click_type or "any"
    if click_type == "any":
        return True
    return any(click_type.lower() in (candidate or "").lower() for candidate in candidates)


def _click_type_matches(trigger: dict, event: Event) -> bool:
    """True if a button-trigger definition's click_type matches what this
    entity state-change event reports - checked against either the new
    state's plain state string (covers e.g. a derived "single_press"
    sensor) or its event_type attribute (covers native event.* entities,
    e.g. Zigbee2MQTT/ZHA reporting "single_push"/"1_single")."""
    new_state = event.data.get("new_state")
    if new_state is None:
        return False
    return _click_type_value_matches(
        trigger.get("click_type"), new_state.state, (new_state.attributes or {}).get("event_type")
    )


def _is_stale_reconnect_event(old_state, new_state) -> bool:
    """True if this looks like a flaky BLE/mesh link re-announcing an old
    button press after reconnecting, rather than a genuine new one. Only
    meaningful for the `event` domain, whose state is always the ISO
    timestamp of when it last fired: a real press always reports a
    timestamp close to now, so a reported timestamp far in the past -
    specifically arriving right after the entity was `unavailable` a
    moment ago, exactly the reconnect signature observed - is almost
    certainly the entity re-transmitting its last cached state rather
    than a fresh physical press."""
    if old_state is None or new_state is None:
        return False
    if old_state.state != "unavailable":
        return False
    if new_state.domain != "event":
        return False
    reported = dt_util.parse_datetime(new_state.state)
    if reported is None:
        return False
    age = (dt_util.utcnow() - dt_util.as_utc(reported)).total_seconds()
    return age > STALE_EVENT_MAX_AGE_SECONDS


def _event_match_ok(trigger: dict, profile: dict, event: Event) -> bool:
    """True if a raw-bus-event trigger's event_match filters (e.g. a
    specific Shelly device_id/channel) all agree with what this event
    reports - a blank/unset field in event_match means "don't filter on
    this one". Compared as trimmed strings since the frontend may store
    some fields (e.g. channel) as numbers while the event itself may report
    them as int or str depending on the integration that fired it."""
    match = trigger.get("event_match") or {}
    for key in profile["match_fields"]:
        expected = match.get(key)
        if expected in (None, ""):
            continue
        if str(event.data.get(key)).strip() != str(expected).strip():
            return False
    return True


def _button_attachments_for_trigger(cfg: dict, trigger_id: str) -> list[tuple[dict, dict | None, dict]]:
    """Every (room, device, attachment) that subscribes to a given button
    trigger definition - device is None for a room-level attachment
    (whole-room toggle/off, or a schedule-wide apply_now/force_period).
    The same trigger can be attached from multiple places at once, unlike
    the old flat one-entry-per-binding list."""
    result: list[tuple[dict, dict | None, dict]] = []
    for room in cfg.get("rooms", []):
        for attachment in room.get("buttons", []):
            if attachment.get("trigger_id") == trigger_id:
                result.append((room, None, attachment))
        for device in room.get("devices", []):
            for attachment in device.get("buttons", []):
                if attachment.get("trigger_id") == trigger_id:
                    result.append((room, device, attachment))
    return result


def _condition_active(hass: HomeAssistant, condition: dict) -> bool:
    entity_id = condition.get("entity_id")
    expected = condition.get("state")
    if not entity_id or not expected:
        return False
    state = hass.states.get(entity_id)
    return state is not None and state.state == expected


def _room_floor_id(hass: HomeAssistant, room: dict) -> str | None:
    """The HA floor a room's Area belongs to (Settings -> Areas -> floor) -
    RoomFlow has no floor concept of its own, it just reads the one HA's
    own floor registry already provides."""
    area_id = room.get("area_id")
    if not area_id:
        return None
    area = ar.async_get(hass).async_get_area(area_id)
    return area.floor_id if area else None


def _active_house_conditions(hass: HomeAssistant, cfg: dict) -> list[str]:
    """IDs of the house-wide conditions (cfg.house_conditions) that are
    currently true, in priority order - same shape/semantics as a room's
    own custom_conditions, just scoped to the whole house instead of one
    room (e.g. replacing the old hus_scener_bortrest/stadning cascade)."""
    return [
        condition["id"]
        for condition in cfg.get("house_conditions", [])
        if _condition_active(hass, condition)
    ]


def _active_floor_conditions(hass: HomeAssistant, cfg: dict, floor_id: str | None) -> list[str]:
    """IDs of the conditions (cfg.floor_conditions) scoped to one floor
    that are currently true, in priority order - only ever non-empty for
    a floor_id an area is actually assigned to."""
    if not floor_id:
        return []
    return [
        condition["id"]
        for condition in cfg.get("floor_conditions", [])
        if condition.get("floor_id") == floor_id and _condition_active(hass, condition)
    ]


def _active_room_conditions(hass: HomeAssistant, room: dict, cfg: dict) -> list[str]:
    """IDs of conditions currently true for this room, in priority order
    (list order = priority, top = highest): the room's own custom
    conditions first, then any active condition shared by its floor (via
    the room's HA Area -> floor assignment), then any active house-wide
    condition - mirroring the old per-room/per-floor/per-house scene
    cascade this replaces (room's own scene beats the floor's, which
    beats the house's)."""
    active = [
        condition["id"]
        for condition in room.get("custom_conditions", [])
        if _condition_active(hass, condition)
    ]
    active.extend(_active_floor_conditions(hass, cfg, _room_floor_id(hass, room)))
    active.extend(_active_house_conditions(hass, cfg))
    return active


def _condition_name(cfg: dict, condition_id: str, room: dict | None = None) -> str | None:
    """Looks up a condition id's display name across every tier it could
    have come from - a room's own custom_conditions (only searched when a
    room is given), then floor_conditions, then house_conditions - so the
    room/floor/house status sensors can show *whichever* tier's condition
    actually won without needing to know which one it was."""
    pools = []
    if room is not None:
        pools.append(room.get("custom_conditions", []))
    pools.append(cfg.get("floor_conditions", []))
    pools.append(cfg.get("house_conditions", []))
    for pool in pools:
        for condition in pool:
            if condition.get("id") == condition_id:
                return condition.get("name")
    return None


def _resolve_status_text(
    cfg: dict,
    active_ids: list[str],
    period: str | None,
    day_type: str,
    home_state: str,
    room: dict | None = None,
) -> str | None:
    """The display text for a room/floor/house status: whichever
    condition is active wins (highest priority first - see
    _active_room_conditions/_active_floor_conditions/
    _active_house_conditions), else away if that applies, else the
    current period name. Shared by the Room/Floor/House status sensors
    (sensor.py) and the Overview tab's status summary (ws_get_dashboard
    in websocket_api.py) so the two can never disagree. The away/
    no-name-active outcomes come back as sentinels (see
    STATUS_SENTINEL_TEXT above), not literal English words - this
    function has no notion of the viewer's language.

    day_type deliberately isn't checked here (there used to be a blanket
    "day_type == weekend -> show Weekend" fallback before period, taking
    priority over it): a schedule that actually distinguishes weekday/
    weekend already does so with separate periods (e.g. "Dag" vs "Helg
    Dag" - see the main schedule), so the period name itself already
    says "weekend" when it should. The blanket fallback only ever
    masked that more specific name behind a generic "Weekend"/"Helg" -
    for a schedule with no such split it simply shows the plain weekday
    period name year-round, which beats a vague, time-of-day-blind
    "Weekend" label."""
    if active_ids:
        return _condition_name(cfg, active_ids[0], room) or STATUS_SENTINEL_ACTIVE
    if home_state == "away":
        return STATUS_SENTINEL_AWAY
    if period:
        return period.capitalize()
    return None


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


def _migrate_default_transitions_nesting(cfg: dict) -> dict:
    """One-time migration: default_transitions used to be a flat
    {period_id: seconds} map, shared by every room via the single old
    global periods list. Now that periods live inside per-schedule lists
    (see CONF_SCHEDULES in const.py), it nests one level deeper by
    schedule id - wrap the old flat shape under DEFAULT_SCHEDULE_ID so
    every existing room (still pointed at that schedule by default) keeps
    its exact transition timings. Detected by value type (the old shape's
    values are plain numbers, the new shape's are dicts) rather than a
    stored version flag, so it's safe to run unconditionally on every
    load."""
    transitions = cfg.get("default_transitions")
    if transitions and not any(isinstance(v, dict) for v in transitions.values()):
        cfg["default_transitions"] = {DEFAULT_SCHEDULE_ID: transitions}
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
    config = _migrate_default_transitions_nesting(config)
    _migrate_entry_data_to_config(entry, config)
    config.setdefault("rooms", [])
    config.setdefault("buttons", [])
    config.setdefault("default_transitions", {DEFAULT_SCHEDULE_ID: dict(DEFAULT_TRANSITIONS)})

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["store"] = store
    hass.data[DOMAIN]["config"] = config
    hass.data[DOMAIN]["entry"] = entry
    hass.data[DOMAIN].setdefault("button_unsubs", [])
    hass.data[DOMAIN].setdefault("button_press_started", {})
    hass.data[DOMAIN].setdefault("hold_dim_timers", {})
    hass.data[DOMAIN].setdefault("hold_dim_pending", {})
    hass.data[DOMAIN].setdefault("hold_dim_direction", {})
    hass.data[DOMAIN].setdefault("motion_unsubs", [])
    hass.data[DOMAIN].setdefault("motion_off_timers", {})
    hass.data[DOMAIN].setdefault("motion_active_state", {})
    hass.data[DOMAIN].setdefault("motion_manual_override", {})
    hass.data[DOMAIN].setdefault("forced_period", {})
    hass.data[DOMAIN].setdefault("last_logged_period", {})
    hass.data[DOMAIN].setdefault("last_applied_signature", {})
    await async_load_logs(hass)

    # Register websocket commands only once
    if not hass.data[DOMAIN].get("ws_registered"):
        from .websocket_api import async_register_commands

        async_register_commands(hass)
        hass.data[DOMAIN]["ws_registered"] = True

    # These three read hass.data[DOMAIN]["config"] fresh on every call rather
    # than closing over values captured once here, so edits saved from the
    # card's Settings tab take effect immediately - no reload needed, same
    # as how _apply_to_rooms already re-reads "default_transitions" below.

    def _get_period(schedule_id: str | None = None) -> str | None:
        cfg = hass.data[DOMAIN]["config"]
        periods = periods_for_schedule(cfg, schedule_id)  # already priority-ordered (top = highest)
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

    def _device_display_name(entity_id: str) -> str:
        state = hass.states.get(entity_id)
        return state.name if state and state.name else entity_id

    def _behavior_state_label(behavior: dict) -> str:
        if behavior.get("state") != "on":
            return "off"
        parts = ["on"]
        if "brightness" in behavior:
            parts.append(f"{round(behavior['brightness'] / 255 * 100)}%")
        if "color_temp_kelvin" in behavior:
            parts.append(f"{behavior['color_temp_kelvin']}K")
        return " ".join(parts)

    def _period_display_name(schedule_id: str, period_id: str | None) -> str:
        if not period_id:
            return "-"
        schedule = next((s for s in infer_schedules(hass.data[DOMAIN]["config"]) if s["id"] == schedule_id), None)
        period = next((p for p in (schedule["periods"] if schedule else []) if p["id"] == period_id), None)
        return period.get("name", period_id) if period else period_id

    def _log_device_action(
        room: dict, device: dict, state_label: str, schedule_id: str, period_id: str | None, source: str
    ) -> None:
        log_device_change(
            hass,
            room_id=room.get("id"),
            room_name=room.get("name", room.get("id")),
            entity_id=device.get("entity_id"),
            device_name=_device_display_name(device.get("entity_id")),
            state_label=state_label,
            period_name=_period_display_name(schedule_id, period_id),
            source=source,
        )

    def _record_period_change(schedule_id: str, period_id: str, source: str) -> None:
        tracker = hass.data[DOMAIN]["last_logged_period"]
        if tracker.get(schedule_id) == period_id:
            return
        tracker[schedule_id] = period_id
        schedule = next((s for s in infer_schedules(hass.data[DOMAIN]["config"]) if s["id"] == schedule_id), None)
        log_period_change(
            hass,
            schedule_id=schedule_id,
            schedule_name=schedule.get("name", schedule_id) if schedule else schedule_id,
            period_id=period_id,
            period_name=_period_display_name(schedule_id, period_id),
            source=source,
        )

    async def _apply_device(
        room: dict,
        device: dict,
        behavior: dict,
        transition: float | None,
        schedule_id: str,
        period_id: str | None,
        source: str,
    ) -> bool:
        try:
            await _apply_behavior(hass, device, behavior, transition)
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "RoomFlow: could not apply behavior to %s: %s",
                device.get("entity_id"),
                err,
            )
            return False
        _log_device_action(room, device, _behavior_state_label(behavior), schedule_id, period_id, source)
        return True

    async def _apply_single_device(
        room: dict,
        device: dict,
        period: str,
        day_type: str,
        home_state: str,
        active_condition_ids: list[str],
        default_transitions: dict,
        schedule_id: str,
        source: str,
        respect_manual_override: bool = False,
    ) -> None:
        raw_behaviors = device.get("behaviors", {}).get(period)
        if not raw_behaviors:
            return
        behaviors = _normalize_behaviors(raw_behaviors)
        control = _control_mode(device, period)
        behavior = _pick_behavior(
            behaviors,
            active_condition_ids,
            day_type,
            home_state,
            default_enabled=control["mode"] != "button",
            away_default=device.get("away_default"),
        )
        if not behavior:
            return

        entity_id = device["entity_id"]
        signature_key = f"{room['id']}:{entity_id}"
        target_signature = _behavior_signature(behavior)

        if respect_manual_override:
            # Ambient ticks (time/day-type/home-state/sun polling) re-resolve
            # and would otherwise re-issue the exact same service call every
            # time they fire, overwriting anything a person just did by hand.
            # If the schedule's own target hasn't moved since we last set it,
            # this re-apply carries no new information - skip it, whether
            # the device still matches (nothing to do) or has since diverged
            # (someone changed it - leave it alone until the target itself
            # actually changes, e.g. the next period/condition/away-state).
            if hass.data[DOMAIN]["last_applied_signature"].get(signature_key) == target_signature:
                return

        device_transitions = device.get("transitions", {}) or {}
        transition = device_transitions.get(period)
        if transition is None:
            transition = default_transitions.get(period)

        applied = await _apply_device(room, device, behavior, transition, schedule_id, period, source)
        if applied:
            hass.data[DOMAIN]["last_applied_signature"][signature_key] = target_signature

    async def _apply_to_rooms(
        rooms: list,
        forced_period: str | None = None,
        respect_motion_control: bool = False,
        respect_manual_override: bool = False,
    ) -> None:
        day_type = _get_day_type()
        home_state = _get_home_state()
        cfg = hass.data[DOMAIN]["config"]

        for room in rooms:
            schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
            if forced_period is not None:
                period = forced_period
                # Remembered so the "Current period" sensor reflects the
                # forced period immediately instead of the stale
                # naturally-resolved value it last computed - cleared again
                # by the next real recompute (_handle_relevant_change) so a
                # forced period never sticks past the condition that should
                # actually be governing the schedule.
                hass.data[DOMAIN]["forced_period"][schedule_id] = forced_period
            else:
                # Resolved per-room (not once for the whole batch) since
                # each room can follow a different schedule (room["schedule_id"])
                # - see const.py's CONF_SCHEDULES docs.
                period = _get_period(schedule_id)
                if period is None:
                    _LOGGER.debug(
                        "RoomFlow: could not resolve current period for room '%s', skipping", room.get("id")
                    )
                    continue

            source = "forced" if forced_period is not None else "schedule"
            _record_period_change(schedule_id, period, source)

            default_transitions = transitions_for_schedule(cfg, schedule_id)
            active_condition_ids = _active_room_conditions(hass, room, cfg)
            for device in room.get("devices", []):
                # Devices whose control mode is "motion" for this period are
                # exclusively controlled by the motion subsystem during
                # routine ambient reapplies (time/day-type/home-state
                # ticking) - otherwise every such tick would force them back
                # on regardless of actual motion. Explicit triggers (Test
                # now, apply_now/force_period buttons) still touch
                # everything, same as before.
                if respect_motion_control and _control_mode(device, period)["mode"] == "motion":
                    continue
                await _apply_single_device(
                    room,
                    device,
                    period,
                    day_type,
                    home_state,
                    active_condition_ids,
                    default_transitions,
                    schedule_id,
                    source,
                    respect_manual_override=respect_manual_override,
                )

        if forced_period is not None:
            # Push the just-recorded override to the "Current period" sensor
            # right away instead of waiting for whatever ambient trigger
            # happens to fire next.
            async_dispatcher_send(hass, SIGNAL_RECOMPUTE)

    async def apply_current_period() -> None:
        cfg = hass.data[DOMAIN]["config"]
        await _apply_to_rooms(cfg.get("rooms", []), respect_motion_control=True, respect_manual_override=True)

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
        entry = hass.data[DOMAIN]["motion_off_timers"].pop(key, None)
        if entry:
            entry["cancel"]()

    def _resolve_manual_on_behavior(
        room: dict, device: dict
    ) -> tuple[dict | None, str, str | None, float | None]:
        """What a manual "on" (button toggle) should apply to this device
        right now - the same Default/Weekend/Away/condition tiers
        _apply_single_device uses, but resolved with `_pick_manual_on_behavior`
        (see its docstring) instead of `_pick_behavior`: an off-resolving
        condition/away override never blocks a manual on, only an
        on-resolving one is honoured, falling through to the period's own
        default otherwise. Ambient/motion ticks separately skip a
        "button" control-mode device's Default variant entirely (see
        _control_mode) - but a manual button press is the *only* trigger
        such a device ever gets, so it always reaches the period's real
        configured brightness/color, never gated on control mode."""
        cfg = hass.data[DOMAIN]["config"]
        schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
        period = _get_period(schedule_id)
        if period is None:
            return None, schedule_id, None, None
        raw_behaviors = device.get("behaviors", {}).get(period)
        if not raw_behaviors:
            return None, schedule_id, period, None
        behaviors = _normalize_behaviors(raw_behaviors)
        behavior = _pick_manual_on_behavior(
            behaviors,
            _active_room_conditions(hass, room, cfg),
            _get_day_type(),
            _get_home_state(),
            away_default=device.get("away_default"),
        )
        if not behavior:
            return None, schedule_id, period, None
        device_transitions = device.get("transitions", {}) or {}
        transition = device_transitions.get(period)
        if transition is None:
            transition = transitions_for_schedule(cfg, schedule_id).get(period)
        return behavior, schedule_id, period, transition

    _DIM_STEP_PERCENT = 10

    async def _dim_device(room: dict, device: dict, direction: str, source: str) -> None:
        if _device_domain(device) != "light":
            return
        key = _motion_key(room["id"], device["entity_id"])
        hass.data[DOMAIN]["motion_manual_override"][key] = True
        _cancel_motion_timer(key)
        state = hass.states.get(device["entity_id"])
        current = (state.attributes.get("brightness") if state and state.state == "on" else 0) or 0
        step = round(255 * _DIM_STEP_PERCENT / 100)
        delta = step if direction == "up" else -step
        new_brightness = max(1, min(255, current + delta))
        try:
            await hass.services.async_call(
                "light", "turn_on", {"entity_id": device["entity_id"], "brightness": new_brightness}, blocking=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning("RoomFlow: could not dim %s: %s", device.get("entity_id"), err)
            return
        schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
        pct = round(new_brightness / 255 * 100)
        _log_device_action(room, device, f"on {pct}%", schedule_id, _get_period(schedule_id), source)

    async def _turn_off_room(room: dict) -> None:
        schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
        for device in room.get("devices", []):
            key = _motion_key(room["id"], device["entity_id"])
            hass.data[DOMAIN]["motion_manual_override"][key] = True
            _cancel_motion_timer(key)
            try:
                await hass.services.async_call(
                    _device_domain(device), "turn_off", {"entity_id": device["entity_id"]}, blocking=True
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "RoomFlow: could not turn off %s: %s", device.get("entity_id"), err
                )
                continue
            _log_device_action(room, device, "off", schedule_id, _get_period(schedule_id), "button_off")

    async def _toggle_room(room: dict) -> None:
        devices = room.get("devices", [])
        if not devices:
            return
        schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
        on_count = 0
        for device in devices:
            state = hass.states.get(device["entity_id"])
            if state and state.state == "on":
                on_count += 1
        turn_on = on_count < (len(devices) / 2)
        for device in devices:
            key = _motion_key(room["id"], device["entity_id"])
            hass.data[DOMAIN]["motion_manual_override"][key] = True
            _cancel_motion_timer(key)
            if turn_on:
                behavior, dev_schedule_id, period, transition = _resolve_manual_on_behavior(room, device)
                await _apply_device(
                    room, device, behavior or {"state": "on"}, transition, dev_schedule_id, period, "button_toggle"
                )
                continue
            try:
                await hass.services.async_call(
                    _device_domain(device), "turn_off", {"entity_id": device["entity_id"]}, blocking=True
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning(
                    "RoomFlow: could not toggle %s: %s", device.get("entity_id"), err
                )
                continue
            _log_device_action(room, device, "off", schedule_id, _get_period(schedule_id), "button_toggle")

    async def _toggle_device(room: dict, device: dict, source: str = "button_toggle") -> None:
        state = hass.states.get(device["entity_id"])
        turn_on = not (state and state.state == "on")
        key = _motion_key(room["id"], device["entity_id"])
        hass.data[DOMAIN]["motion_manual_override"][key] = True
        _cancel_motion_timer(key)
        if turn_on:
            behavior, schedule_id, period, transition = _resolve_manual_on_behavior(room, device)
            await _apply_device(room, device, behavior or {"state": "on"}, transition, schedule_id, period, source)
            return
        try:
            await hass.services.async_call(
                _device_domain(device), "turn_off", {"entity_id": device["entity_id"]}, blocking=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "RoomFlow: could not toggle %s: %s", device.get("entity_id"), err
            )
            return
        schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
        _log_device_action(room, device, "off", schedule_id, _get_period(schedule_id), source)

    hass.data[DOMAIN]["apply_fn"] = apply_current_period
    hass.data[DOMAIN]["apply_room_fn"] = apply_room

    # ---------- Physical buttons ----------

    async def _handle_button_press(trigger: dict, event: Event) -> None:
        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if old_state is None:
            # Avoid triggering on HA restart / entity just appearing
            return
        click_type = trigger.get("click_type") or "any"

        if _is_stale_reconnect_event(old_state, new_state):
            log_button_press(
                hass,
                trigger_name=trigger.get("name") or trigger.get("entity_id") or "?",
                entity_id=trigger.get("entity_id"),
                state_label=new_state.state if new_state else "?",
                outcome="stale_reconnect",
                detail=click_type,
            )
            return

        if click_type in TIMED_CLICK_TYPES:
            await _handle_timed_button_press(trigger, event, new_state, click_type)
            return

        if click_type == CLICK_TYPE_HOLD:
            await _handle_hold_button_press(trigger, new_state)
            return

        state_label = new_state.state if new_state else "?"
        trigger_name = trigger.get("name") or trigger.get("entity_id") or "?"

        # Log every recognized state change on this entity regardless of
        # outcome - not just successful runs - so "is Home Assistant even
        # seeing this press" is answerable from the card's Buttons tab
        # instead of only from server logs.
        if not _click_type_matches(trigger, event):
            log_button_press(
                hass,
                trigger_name=trigger_name,
                entity_id=trigger.get("entity_id"),
                state_label=state_label,
                outcome="click_type_mismatch",
                detail=trigger.get("click_type"),
            )
            return

        cfg = hass.data[DOMAIN]["config"]
        attachments = _button_attachments_for_trigger(cfg, trigger.get("id"))
        for room, device, attachment in attachments:
            await _run_button_attachment(room, device, attachment, trigger)

        log_button_press(
            hass,
            trigger_name=trigger_name,
            entity_id=trigger.get("entity_id"),
            state_label=state_label,
            outcome="ran" if attachments else "no_attachments",
            detail=str(len(attachments)) if attachments else None,
        )

    async def _handle_timed_button_press(
        trigger: dict, event: Event, new_state, click_type: str
    ) -> None:
        """Derive short_press_timed/long_press_timed from a plain
        press/release pair (hardware with no click-duration classification
        of its own, e.g. Plejd's event.* button entities, which only ever
        report "press"/"release") by timing the gap between the two -
        unlike every other click_type, this can't be matched against a
        single state-change event in isolation."""
        if new_state is None:
            # Entity went unavailable/was removed - no press/release value
            # to classify.
            return
        entity_id = trigger.get("entity_id")
        trigger_name = trigger.get("name") or entity_id or "?"
        candidates = [new_state.state or "", (new_state.attributes or {}).get("event_type") or ""]
        is_release = any("release" in c.lower() for c in candidates)
        is_press = not is_release and any("press" in c.lower() for c in candidates)

        if is_press:
            hass.data[DOMAIN]["button_press_started"][entity_id] = event.time_fired
            return
        if not is_release:
            return

        # Read, don't pop: a second trigger bound to the same entity (e.g.
        # the paired short/long trigger on the same physical button) needs
        # to independently read this same start time when its own listener
        # processes this same release event.
        started = hass.data[DOMAIN]["button_press_started"].get(entity_id)
        if started is None:
            # No matching press seen (e.g. right after a restart) - can't
            # classify this release.
            return

        threshold_ms = trigger.get("long_press_ms") or DEFAULT_LONG_PRESS_MS
        elapsed_ms = (event.time_fired - started).total_seconds() * 1000
        resolved = CLICK_TYPE_LONG_TIMED if elapsed_ms >= threshold_ms else CLICK_TYPE_SHORT_TIMED
        state_label = f"{resolved} ({elapsed_ms:.0f}ms)"

        if resolved != click_type:
            log_button_press(
                hass,
                trigger_name=trigger_name,
                entity_id=entity_id,
                state_label=state_label,
                outcome="click_type_mismatch",
                detail=click_type,
            )
            return

        cfg = hass.data[DOMAIN]["config"]
        attachments = _button_attachments_for_trigger(cfg, trigger.get("id"))
        for room, device, attachment in attachments:
            await _run_button_attachment(room, device, attachment, trigger)

        log_button_press(
            hass,
            trigger_name=trigger_name,
            entity_id=entity_id,
            state_label=state_label,
            outcome="ran" if attachments else "no_attachments",
            detail=str(len(attachments)) if attachments else None,
        )

    def _start_hold_dim(room: dict, device: dict) -> None:
        if _device_domain(device) != "light":
            return
        key = _motion_key(room["id"], device["entity_id"])
        if key in hass.data[DOMAIN]["hold_dim_timers"]:
            return  # already ramping - a duplicate press event, don't stack timers
        hass.data[DOMAIN]["motion_manual_override"][key] = True
        _cancel_motion_timer(key)

        state = hass.states.get(device["entity_id"])
        current = (state.attributes.get("brightness") if state and state.state == "on" else 0) or 0
        pct = current / 255 * 100
        if pct > 80:
            direction = "down"
        elif pct < 20:
            direction = "up"
        else:
            # Alternate from whichever direction the last hold used, so
            # repeated holds in the comfortable middle range ping-pong
            # instead of always ramping the same way.
            direction = hass.data[DOMAIN]["hold_dim_direction"].get(key, "up")
        hass.data[DOMAIN]["hold_dim_direction"][key] = "down" if direction == "up" else "up"

        async def _tick(_now) -> None:
            tick_state = hass.states.get(device["entity_id"])
            tick_current = (
                tick_state.attributes.get("brightness") if tick_state and tick_state.state == "on" else 0
            ) or 0
            delta = HOLD_DIM_STEP if direction == "up" else -HOLD_DIM_STEP
            new_brightness = max(1, min(255, tick_current + delta))
            try:
                await hass.services.async_call(
                    "light", "turn_on", {"entity_id": device["entity_id"], "brightness": new_brightness}
                )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("RoomFlow: could not hold-dim %s: %s", device.get("entity_id"), err)

        hass.data[DOMAIN]["hold_dim_timers"][key] = async_track_time_interval(
            hass, _tick, timedelta(seconds=HOLD_DIM_INTERVAL_SECONDS)
        )

    async def _handle_hold_button_press(trigger: dict, new_state) -> None:
        """Start/stop a continuous brightness ramp on every hold_dim
        attachment for this trigger, for as long as the button is held.
        Domain-aware press/release detection so the same mechanism covers
        both an `event.*` entity (Plejd/Zigbee-style press/release) and a
        `binary_sensor.*` entity (a Shelly channel's own *_input sensor,
        "on" for exactly as long as the physical button is held) - see
        CLICK_TYPE_HOLD's docstring in const.py for why a raw device-event
        trigger can't drive this at all. Ramping doesn't actually start
        until DEFAULT_LONG_PRESS_MS after the press (see the pending-timer
        dance below) so a plain short click - which also briefly reports
        "on"/"press" on the same entity - never nudges the brightness,
        even if a separate toggle trigger shares the same physical button."""
        entity_id = trigger.get("entity_id")
        trigger_name = trigger.get("name") or entity_id or "?"
        if not entity_id or new_state is None:
            return
        domain = entity_id.split(".")[0]
        if domain == "binary_sensor":
            is_press = new_state.state == "on"
            is_release = new_state.state == "off"
        else:
            candidates = [new_state.state or "", (new_state.attributes or {}).get("event_type") or ""]
            is_release = any("release" in c.lower() for c in candidates)
            is_press = not is_release and any("press" in c.lower() for c in candidates)
        if not is_press and not is_release:
            return

        cfg = hass.data[DOMAIN]["config"]
        attachments = [
            (room, device)
            for room, device, attachment in _button_attachments_for_trigger(cfg, trigger.get("id"))
            if attachment.get("action") == "hold_dim" and device is not None
        ]

        if is_press:
            for room, device in attachments:
                key = _motion_key(room["id"], device["entity_id"])
                # Don't start ramping the instant the input goes "on" - a
                # plain short click holds it "on" too, just for under
                # DEFAULT_LONG_PRESS_MS, and would otherwise nudge the
                # brightness by a tick or two on every ordinary click if a
                # toggle trigger shares the same physical button. Wait to
                # confirm this is actually a hold before touching the light.
                async def _confirm_hold(_now, room=room, device=device, key=key) -> None:
                    hass.data[DOMAIN]["hold_dim_pending"].pop(key, None)
                    _start_hold_dim(room, device)

                hass.data[DOMAIN]["hold_dim_pending"][key] = async_call_later(
                    hass, DEFAULT_LONG_PRESS_MS / 1000, _confirm_hold
                )
        else:
            for room, device in attachments:
                key = _motion_key(room["id"], device["entity_id"])
                pending_cancel = hass.data[DOMAIN]["hold_dim_pending"].pop(key, None)
                if pending_cancel:
                    pending_cancel()  # released before the hold was confirmed - never started ramping
                cancel = hass.data[DOMAIN]["hold_dim_timers"].pop(key, None)
                if cancel:
                    cancel()

        log_button_press(
            hass,
            trigger_name=trigger_name,
            entity_id=entity_id,
            state_label="held" if is_press else "released",
            outcome="ran" if attachments else "no_attachments",
            detail=str(len(attachments)) if attachments else None,
        )

    async def _handle_button_raw_event(trigger: dict, profile: dict, event: Event) -> None:
        # Unlike the entity path above, a raw bus event only ever fires
        # from an actual physical action - HA never replays one
        # synthetically on restart/entity-registration - so there's no
        # analogous "old_state is None" startup guard needed here.
        if not _event_match_ok(trigger, profile, event):
            # Different physical device/channel sharing the same event
            # type (e.g. a second Shelly button elsewhere in the house) -
            # stay silent here, not a click_type_mismatch, to avoid a
            # confusing log row every time an unrelated button is pressed.
            return

        click_value = event.data.get(profile["click_type_field"])
        state_label = str(click_value) if click_value is not None else "?"
        trigger_name = trigger.get("name") or "?"

        if not _click_type_value_matches(trigger.get("click_type"), click_value):
            log_button_press(
                hass,
                trigger_name=trigger_name,
                entity_id=None,
                state_label=state_label,
                outcome="click_type_mismatch",
                detail=trigger.get("click_type"),
            )
            return

        cfg = hass.data[DOMAIN]["config"]
        attachments = _button_attachments_for_trigger(cfg, trigger.get("id"))
        for room, device, attachment in attachments:
            await _run_button_attachment(room, device, attachment, trigger)

        log_button_press(
            hass,
            trigger_name=trigger_name,
            entity_id=None,
            state_label=state_label,
            outcome="ran" if attachments else "no_attachments",
            detail=str(len(attachments)) if attachments else None,
        )

    async def _run_button_attachment(
        room: dict, device: dict | None, attachment: dict, trigger: dict
    ) -> None:
        # device is set for a per-device attachment (toggle/off just that
        # device); None for a room-level attachment (toggle/off the whole
        # room by majority vote, or a schedule-wide action).
        action = attachment.get("action")
        try:
            if action == "toggle":
                if device:
                    await _toggle_device(room, device)
                else:
                    await _toggle_room(room)
            elif action == "off":
                if device:
                    await _turn_off_device(room, device, "button_off")
                else:
                    await _turn_off_room(room)
            elif action == "apply_now":
                await apply_room(room["id"])
            elif action == "force_period":
                await _apply_to_rooms([room], forced_period=attachment.get("force_period"))
            elif action in ("dim_up", "dim_down"):
                # Device-only, like the per-device toggle/off attachment -
                # dimming a whole room in lockstep isn't useful, so this
                # action simply doesn't exist on a room-level attachment.
                if device:
                    await _dim_device(room, device, "up" if action == "dim_up" else "down", "button_dim")
            elif action == "toggle_condition":
                # Room-level only, like apply_now/force_period - a custom
                # condition (e.g. "Mys") belongs to the room, not to any one
                # device, so this toggles the helper entity it's defined
                # against directly (almost always an input_boolean) rather
                # than resolving/applying a light behavior at all.
                condition = next(
                    (c for c in room.get("custom_conditions", []) if c.get("id") == attachment.get("condition_id")),
                    None,
                )
                if condition and condition.get("entity_id"):
                    await hass.services.async_call(
                        "homeassistant", "toggle", {"entity_id": condition["entity_id"]}, blocking=True
                    )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "RoomFlow: error handling button press (%s): %s",
                trigger.get("entity_id"),
                err,
            )

    def _setup_button_listeners() -> None:
        for unsub in hass.data[DOMAIN].get("button_unsubs", []):
            unsub()
        unsubs = []
        triggers = hass.data[DOMAIN]["config"].get("button_triggers", [])
        for trigger in triggers:
            if trigger.get("source") == "event":
                profile = EVENT_DEVICE_PROFILES.get(trigger.get("profile"))
                if not profile:
                    _LOGGER.warning(
                        "RoomFlow: unknown button event profile '%s' for trigger '%s'",
                        trigger.get("profile"),
                        trigger.get("name"),
                    )
                    continue

                def _make_event_handler(trg, prof):
                    async def _handler(event: Event) -> None:
                        await _handle_button_raw_event(trg, prof, event)

                    return _handler

                unsubs.append(
                    hass.bus.async_listen(profile["event_type"], _make_event_handler(trigger, profile))
                )
                continue

            entity_id = trigger.get("entity_id")
            if not entity_id:
                continue

            def _make_handler(trg):
                async def _handler(event: Event) -> None:
                    await _handle_button_press(trg, event)

                return _handler

            unsubs.append(
                async_track_state_change_event(hass, [entity_id], _make_handler(trigger))
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

    def _is_definition_active(definition: dict) -> bool:
        triggers = definition.get("triggers", [])
        return any(_is_trigger_active(t) for t in triggers)

    def _motion_trigger_just_pulsed(definition: dict, event: Event) -> bool:
        """True if this specific state-change event is a "motion"-type
        trigger (not threshold_above) genuinely transitioning to "on" - a
        real presence pulse, as opposed to the combined definition merely
        staying active because a different trigger (e.g. humidity sitting
        above its threshold for a long time) never dropped. Used to
        re-light a motion_on device that's unexpectedly off even when the
        aggregate active flag was already true and so wouldn't otherwise
        cause anything to re-apply - a sticky secondary trigger shouldn't
        be able to swallow every later, genuine motion pulse."""
        changed_entity_id = event.data.get("entity_id")
        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")
        if new_state is None or new_state.state != "on":
            return False
        if old_state is not None and old_state.state == "on":
            return False
        return any(
            trigger.get("entity_id") == changed_entity_id and trigger.get("type", "motion") == "motion"
            for trigger in definition.get("triggers", [])
        )

    def _motion_on_devices(room: dict, period: str, definition_id: str) -> list:
        """Devices to turn on when the given motion-sensor definition
        becomes active this period - control mode "motion", subscribed to
        this specific definition, with motion_on enabled."""
        result = []
        for device in room.get("devices", []):
            control = _control_mode(device, period)
            if (
                control["mode"] == "motion"
                and control["motion_sensor_id"] == definition_id
                and control["motion_on"]
            ):
                result.append(device)
        return result

    def _motion_off_devices(room: dict, period: str, definition_id: str) -> list:
        """Devices to schedule off when the given motion-sensor definition
        becomes inactive this period - control mode "motion", subscribed
        to this specific definition, with motion_off enabled."""
        result = []
        for device in room.get("devices", []):
            control = _control_mode(device, period)
            if control["mode"] != "motion" or control["motion_sensor_id"] != definition_id:
                continue
            if control["motion_off"]:
                result.append(device)
        return result

    async def _turn_off_device(room: dict, device: dict, source: str = "motion_off") -> None:
        try:
            await hass.services.async_call(
                _device_domain(device), "turn_off", {"entity_id": device["entity_id"]}, blocking=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "RoomFlow: could not turn off %s: %s", device.get("entity_id"), err
            )
            return
        schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
        _log_device_action(room, device, "off", schedule_id, _get_period(schedule_id), source)

    async def _dim_device_for_warning(room: dict, device: dict, brightness: float) -> None:
        if _device_domain(device) != "light":
            return  # the dim-warning stage only makes sense for lights
        try:
            await hass.services.async_call(
                "light", "turn_on", {"entity_id": device["entity_id"], "brightness": brightness}, blocking=True
            )
        except Exception as err:  # noqa: BLE001
            _LOGGER.warning(
                "RoomFlow: could not dim %s for motion warning: %s", device.get("entity_id"), err
            )
            return
        schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
        _log_device_action(
            room, device, f"on {round(brightness / 255 * 100)}%", schedule_id, _get_period(schedule_id), "motion_warn"
        )

    async def _apply_motion_device_on(room: dict, device: dict, source: str = "motion_on") -> None:
        schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
        period = _get_period(schedule_id)
        if period is None:
            return
        day_type = _get_day_type()
        home_state = _get_home_state()
        cfg = hass.data[DOMAIN]["config"]
        active_condition_ids = _active_room_conditions(hass, room, cfg)
        default_transitions = transitions_for_schedule(cfg, schedule_id)
        await _apply_single_device(
            room, device, period, day_type, home_state, active_condition_ids, default_transitions, schedule_id, source
        )

    def _schedule_motion_off(room_id: str, device: dict, motion_cfg: dict) -> None:
        entity_id = device["entity_id"]
        key = _motion_key(room_id, entity_id)
        device_motion_cfg = device.get("motion", {})
        off_delay = device_motion_cfg.get("off_delay_minutes")
        if off_delay is None:
            off_delay = motion_cfg.get("timeout_minutes", 10)
        # A real motion sensor typically keeps reporting "on" for a while
        # after actual movement stops (a hardware/firmware hold time that
        # varies per sensor model) - the binary_sensor going "off" already
        # has that baked in, so counting the full configured timeout from
        # there would overshoot the time the user actually intends by that
        # same amount. Subtract the largest hold_seconds among this
        # definition's own motion-type triggers so the total elapsed time
        # since the person actually left matches what was configured.
        hold_seconds = max(
            (t.get("hold_seconds", 0) or 0 for t in motion_cfg.get("triggers", []) if t.get("type", "motion") == "motion"),
            default=0,
        )
        off_delay = max(0.0, off_delay - hold_seconds / 60)
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
                await _turn_off_device(final_room, final_device, "motion_warn_expired")

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
                await _dim_device_for_warning(current_room, current_device, warn_brightness)
                cancel = async_call_later(hass, warn_minutes * 60, _after_warn)
                hass.data[DOMAIN]["motion_off_timers"][key] = {
                    "cancel": cancel,
                    "next_action": "off",
                    "fires_at": dt_util.utcnow() + timedelta(minutes=warn_minutes),
                }
            else:
                await _turn_off_device(current_room, current_device)

        # Exposed to the frontend (see ws_get_dashboard) so the Overview
        # tab can show a live countdown under the room - "next_action" is
        # what happens when *this* timer fires: dims first if warn_enabled,
        # otherwise this is already the final off.
        _cancel_motion_timer(key)
        cancel = async_call_later(hass, off_delay * 60, _after_off_delay)
        hass.data[DOMAIN]["motion_off_timers"][key] = {
            "cancel": cancel,
            "next_action": "dim" if warn_enabled else "off",
            "fires_at": dt_util.utcnow() + timedelta(minutes=off_delay),
        }

    async def _handle_motion_change(definition_id: str, event: Event) -> None:
        cfg = hass.data[DOMAIN]["config"]
        definition = next(
            (m for m in cfg.get("motion_sensors", []) if m.get("id") == definition_id), None
        )
        if not definition:
            return

        new_active = _is_definition_active(definition)
        previous_active = hass.data[DOMAIN]["motion_active_state"].get(definition_id, False)

        if new_active and previous_active and _motion_trigger_just_pulsed(definition, event):
            for room in cfg.get("rooms", []):
                schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
                period = _get_period(schedule_id)
                if period is None:
                    continue
                for device in _motion_on_devices(room, period, definition_id):
                    state = hass.states.get(device["entity_id"])
                    if state and state.state == "on":
                        continue
                    key = _motion_key(room["id"], device["entity_id"])
                    hass.data[DOMAIN]["motion_manual_override"].pop(key, None)
                    _cancel_motion_timer(key)
                    await _apply_motion_device_on(room, device)

        if new_active == previous_active:
            return
        hass.data[DOMAIN]["motion_active_state"][definition_id] = new_active

        # A definition can be subscribed to by devices scattered across
        # several rooms (that's the point - a shared, reusable trigger set)
        # so every room needs checking, not just one.
        for room in cfg.get("rooms", []):
            schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
            period = _get_period(schedule_id)
            if period is None:
                continue

            if new_active:
                restored = set()
                for device in _motion_on_devices(room, period, definition_id):
                    key = _motion_key(room["id"], device["entity_id"])
                    # A fresh motion cycle always releases any manual-mode
                    # lock from a prior button press, per RoomFlow's design.
                    hass.data[DOMAIN]["motion_manual_override"].pop(key, None)
                    _cancel_motion_timer(key)
                    await _apply_motion_device_on(room, device)
                    restored.add(device["entity_id"])
                # A motion_off-only device (e.g. turned on by a bound button,
                # then left to motion purely to dim-and-turn-off after
                # inactivity) never went through _motion_on_devices above, so
                # it needs its own restore path here: if motion returns while
                # its off-timer/dim-warning is still counting down, that's an
                # in-progress countdown being interrupted, not a fresh
                # "motion turned this on" event - gated on an actual pending
                # timer existing, not on motion_on (which is off for these).
                for device in _motion_off_devices(room, period, definition_id):
                    if device["entity_id"] in restored:
                        continue
                    key = _motion_key(room["id"], device["entity_id"])
                    if key not in hass.data[DOMAIN]["motion_off_timers"]:
                        continue
                    _cancel_motion_timer(key)
                    await _apply_motion_device_on(room, device, source="motion_restored")
            else:
                for device in _motion_off_devices(room, period, definition_id):
                    key = _motion_key(room["id"], device["entity_id"])
                    if hass.data[DOMAIN]["motion_manual_override"].get(key):
                        continue
                    _schedule_motion_off(room["id"], device, definition)

    def _setup_motion_listeners() -> None:
        for unsub in hass.data[DOMAIN].get("motion_unsubs", []):
            unsub()
        for entry in hass.data[DOMAIN].get("motion_off_timers", {}).values():
            entry["cancel"]()
        hass.data[DOMAIN]["motion_off_timers"] = {}
        hass.data[DOMAIN]["motion_active_state"] = {}
        hass.data[DOMAIN]["motion_manual_override"] = {}

        unsubs = []
        definitions = hass.data[DOMAIN]["config"].get("motion_sensors", [])
        for definition in definitions:
            triggers = definition.get("triggers", [])
            entity_ids = [t.get("entity_id") for t in triggers if t.get("entity_id")]
            if not entity_ids:
                continue

            hass.data[DOMAIN]["motion_active_state"][definition["id"]] = _is_definition_active(definition)

            def _make_handler(definition_id):
                async def _handler(event: Event) -> None:
                    await _handle_motion_change(definition_id, event)

                return _handler

            unsubs.append(
                async_track_state_change_event(hass, entity_ids, _make_handler(definition["id"]))
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
        # A real ambient trigger firing means whatever period a button
        # forced earlier is no longer the last word - let the naturally
        # resolved period win again.
        hass.data[DOMAIN]["forced_period"].clear()
        await apply_current_period()
        async_dispatcher_send(hass, SIGNAL_RECOMPUTE)

    def _setup_time_listeners() -> None:
        for unsub in hass.data[DOMAIN].get("time_unsubs", []):
            unsub()

        cfg = hass.data[DOMAIN]["config"]
        # Every schedule's periods need listeners, regardless of which
        # rooms currently follow which schedule - a room can be pointed at
        # a different schedule at any time from the card, with no reload.
        periods = [period for schedule in infer_schedules(cfg) for period in schedule["periods"]]
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
        for condition in cfg.get("floor_conditions", []) + cfg.get("house_conditions", []):
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

    # REMOVED (v0.0.41): this used to mirror every registered Lovelace
    # resource into RoomFlow's own panel via add_extra_js_url, so a custom
    # icon pack (e.g. a "phu:some-icon" namespace) would resolve here too,
    # not just on a real dashboard. That mechanism - `extra_module_url` -
    # races Home Assistant's own frontend bootstrap: app.js swaps
    # `window.customElements` for a scoped registry shim while these
    # extra modules are loading concurrently, and whichever side loses the
    # race throws "Failed to execute 'define' ... already been used with
    # this registry" - breaking the *entire* frontend (sidebar, every
    # dashboard), not just RoomFlow's own panel. Confirmed live: with this
    # block active alongside ~35 HACS card resources, every single page
    # load crashed; disabling RoomFlow's config entry alone (with
    # everything else untouched) took it from 8/8 crashes to 0/8. See
    # https://github.com/aex351/home-assistant-neerslag-card/issues/58 for
    # the same race in another integration, and its own recommendation:
    # don't use extra_module_url for anything that isn't the one panel
    # script itself - a real Lovelace resource (loaded by the frontend
    # itself, after bootstrap, not racing it) is the only safe way to add
    # a script to every page. Custom icon packs not resolving inside
    # RoomFlow's own panel is a real, known regression from removing this
    # - accepted deliberately over the alternative (the regression this
    # was fixing was cosmetic; this one took down the whole app).

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
            await hass.services.async_call("light", "turn_on", service_data, blocking=True)
        else:
            await hass.services.async_call("light", "turn_off", service_data, blocking=True)
    elif device_type == DEVICE_TYPE_OUTLET:
        service = "turn_on" if state == "on" else "turn_off"
        await hass.services.async_call("switch", service, {"entity_id": entity_id}, blocking=True)


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
    for entry in hass.data[DOMAIN].get("motion_off_timers", {}).values():
        entry["cancel"]()
    for cancel in hass.data[DOMAIN].get("hold_dim_timers", {}).values():
        cancel()
    for cancel in hass.data[DOMAIN].get("hold_dim_pending", {}).values():
        cancel()
    try:
        async_remove_panel(hass, "roomflow")
    except ValueError:
        pass
    hass.data.pop(DOMAIN, None)
    return True
