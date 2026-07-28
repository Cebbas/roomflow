"""RoomFlow sensor entities.

These are real Home Assistant entities: they show up in Developer Tools ->
States, can be used in any automation, and - like any entity - can be
renamed and assigned to an area from their entity settings (the gear icon
next to the entity, or Settings -> Devices & services -> Entities).
"""
from __future__ import annotations

import re

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import _active_room_conditions
from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
    DEFAULT_DEVICE_NAME,
    SIGNAL_RECOMPUTE,
    infer_schedules,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            RoomFlowDayTypeSensor(hass, entry),
            RoomFlowHomeStateSensor(hass, entry),
        ]
    )

    hass.data[DOMAIN].setdefault("schedule_period_entities", {})

    def _refresh_schedule_period_sensors() -> None:
        cfg = hass.data[DOMAIN]["config"]
        schedules = infer_schedules(cfg)
        existing = hass.data[DOMAIN]["schedule_period_entities"]
        current_schedule_ids = {schedule["id"] for schedule in schedules}

        for schedule_id in list(existing):
            if schedule_id not in current_schedule_ids:
                entity = existing.pop(schedule_id)
                hass.async_create_task(entity.async_remove(force_remove=True))

        new_entities = []
        for schedule in schedules:
            if schedule["id"] not in existing:
                entity = RoomFlowSchedulePeriodSensor(hass, entry, schedule["id"])
                existing[schedule["id"]] = entity
                new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    hass.data[DOMAIN]["refresh_schedule_sensors_fn"] = _refresh_schedule_period_sensors
    _refresh_schedule_period_sensors()

    hass.data[DOMAIN].setdefault("room_status_entities", {})

    def _refresh_room_status_sensors() -> None:
        cfg = hass.data[DOMAIN]["config"]
        rooms = cfg.get("rooms", [])
        existing = hass.data[DOMAIN]["room_status_entities"]
        current_room_ids = {room["id"] for room in rooms}

        for room_id in list(existing):
            if room_id not in current_room_ids:
                entity = existing.pop(room_id)
                hass.async_create_task(entity.async_remove(force_remove=True))

        new_entities = []
        for room in rooms:
            if room["id"] not in existing:
                entity = RoomFlowRoomStatusSensor(hass, entry, room["id"])
                existing[room["id"]] = entity
                new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

        # Best-effort: keep each already-existing room sensor's device area/
        # name in sync with the room (rename, or moved to a different area).
        # A brand-new entity's device already gets the right area/name at
        # creation time via its own DeviceInfo, so this only matters for
        # entities that already existed before this refresh.
        device_registry = dr.async_get(hass)
        for room in rooms:
            if room["id"] not in existing:
                continue
            device = device_registry.async_get_device(identifiers={(DOMAIN, f"room_{room['id']}")})
            if device:
                device_registry.async_update_device(
                    device.id, area_id=room.get("area_id"), name=room.get("name")
                )

    hass.data[DOMAIN]["refresh_rooms_fn"] = _refresh_room_status_sensors
    _refresh_room_status_sensors()


class _RoomFlowBaseSensor(SensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
        options: list[str] | None = None,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon
        if options is not None:
            # Fixed, known vocabulary (day type/home state) - periods are
            # user-editable so RoomFlowPeriodSensor below doesn't set this.
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = options
        config = hass.data.get(DOMAIN, {}).get("config", {})
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=config.get(CONF_DEVICE_NAME, DEFAULT_DEVICE_NAME),
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        self._update_state()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_RECOMPUTE, self._handle_signal)
        )

    @callback
    def _handle_signal(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        raise NotImplementedError


class RoomFlowSchedulePeriodSensor(_RoomFlowBaseSensor):
    """Current period's display name for one specific schedule, resolved
    from whichever condition group wins right now for that schedule (see
    _get_period in __init__.py). One of these exists per schedule (see
    const.py's CONF_SCHEDULES), living in that schedule's own device
    (like binary_sensor.py's per-period sensors) instead of the shared
    RoomFlow device - so two schedules can't collide, and it's obvious at
    a glance which schedule a "Current period" value belongs to. Periods
    are a user-editable list, so - unlike day type/home state - this has
    no fixed vocabulary and isn't an ENUM."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, schedule_id: str) -> None:
        self._schedule_id = schedule_id
        super().__init__(
            hass,
            entry,
            key=f"{schedule_id}_current_period",
            name="Current period",
            icon="mdi:clock-outline",
        )
        schedule = self._schedule()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"schedule_{schedule_id}")},
            name=schedule.get("name") if schedule else schedule_id,
            entry_type=DeviceEntryType.SERVICE,
        )

    def _schedule(self) -> dict | None:
        cfg = self.hass.data.get(DOMAIN, {}).get("config", {})
        return next((s for s in infer_schedules(cfg) if s["id"] == self._schedule_id), None)

    def _update_state(self) -> None:
        get_period_fn = self.hass.data.get(DOMAIN, {}).get("get_period_fn")
        period_id = get_period_fn(self._schedule_id) if get_period_fn else None
        if period_id is None:
            self._attr_native_value = None
            return
        schedule = self._schedule()
        period = next((p for p in (schedule["periods"] if schedule else []) if p.get("id") == period_id), None)
        self._attr_native_value = period.get("name", period_id) if period else period_id


class RoomFlowDayTypeSensor(_RoomFlowBaseSensor):
    """Whether today counts as "weekday" or "weekend" (always "weekday" if
    day-type isn't configured)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            entry,
            key="day_type",
            name="Day type",
            icon="mdi:calendar-week",
            options=["weekday", "weekend"],
        )

    def _update_state(self) -> None:
        get_day_type_fn = self.hass.data.get(DOMAIN, {}).get("get_day_type_fn")
        self._attr_native_value = get_day_type_fn() if get_day_type_fn else "weekday"


class RoomFlowHomeStateSensor(_RoomFlowBaseSensor):
    """Whether the configured home/away source currently counts as "home" or
    "away" (always "home" if home/away isn't configured)."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            entry,
            key="home_state",
            name="Home state",
            icon="mdi:home-account",
            options=["home", "away"],
        )

    def _update_state(self) -> None:
        get_home_state_fn = self.hass.data.get(DOMAIN, {}).get("get_home_state_fn")
        self._attr_native_value = get_home_state_fn() if get_home_state_fn else "home"


# A plain [^a-z0-9]+ strip would turn any å/ä/ö into an underscore (e.g.
# "Städning" -> "st_dning") - transliterate the common ones first so
# condition names in Swedish (or similar) produce readable attribute keys.
_TRANSLITERATE = str.maketrans("åäöÅÄÖ", "aaoaao")


def _slugify(name: str, existing: set[str]) -> str:
    ascii_name = name.translate(_TRANSLITERATE)
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_name.strip().lower()).strip("_") or "condition"
    if slug not in existing:
        return slug
    i = 2
    while f"{slug}_{i}" in existing:
        i += 1
    return f"{slug}_{i}"


class RoomFlowRoomStatusSensor(SensorEntity):
    """A room's current status: the name of whichever custom condition is
    currently active (highest priority first), else "Away"/"Weekend" if
    those apply, else the current period - mirroring how this device/period
    behavior is already picked (see _pick_behavior/_active_room_conditions
    in __init__.py), just without a specific device. Lives in its own
    device so it can be assigned to the room's own area, unlike the shared
    "RoomFlow" device the other sensors use.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, room_id: str) -> None:
        self.hass = hass
        self._entry = entry
        self._room_id = room_id
        self._attr_unique_id = f"{entry.entry_id}_room_{room_id}_status"
        self._attr_name = "Status"
        self._attr_icon = "mdi:home-outline"
        self._refresh_device_info()

    def _refresh_device_info(self) -> None:
        room = self._room()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"room_{self._room_id}")},
            name=room.get("name", "Room") if room else "Room",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _room(self) -> dict | None:
        cfg = self.hass.data.get(DOMAIN, {}).get("config", {})
        return next((r for r in cfg.get("rooms", []) if r.get("id") == self._room_id), None)

    async def async_added_to_hass(self) -> None:
        self._update_state()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_RECOMPUTE, self._handle_signal)
        )

    @callback
    def _handle_signal(self) -> None:
        self._update_state()
        self.async_write_ha_state()

    def _update_state(self) -> None:
        room = self._room()
        if room is None:
            self._attr_native_value = None
            self._attr_extra_state_attributes = {}
            return

        domain_data = self.hass.data.get(DOMAIN, {})
        get_period_fn = domain_data.get("get_period_fn")
        get_day_type_fn = domain_data.get("get_day_type_fn")
        get_home_state_fn = domain_data.get("get_home_state_fn")
        period = get_period_fn(room.get("schedule_id")) if get_period_fn else None
        day_type = get_day_type_fn() if get_day_type_fn else "weekday"
        home_state = get_home_state_fn() if get_home_state_fn else "home"

        conditions = room.get("custom_conditions", [])
        active_ids = _active_room_conditions(self.hass, room)

        if active_ids:
            winning = next((c for c in conditions if c.get("id") == active_ids[0]), None)
            status = winning["name"] if winning and winning.get("name") else "Active"
        elif home_state == "away":
            status = "Away"
        elif day_type == "weekend":
            status = "Weekend"
        elif period:
            status = period.capitalize()
        else:
            status = None

        active_id_set = set(active_ids)
        attributes: dict[str, bool] = {}
        used_keys: set[str] = set()
        for condition in conditions:
            name = condition.get("name")
            if not name:
                continue
            key = _slugify(name, used_keys)
            used_keys.add(key)
            attributes[key] = condition.get("id") in active_id_set

        self._attr_native_value = status
        self._attr_extra_state_attributes = attributes
