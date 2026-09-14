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
from homeassistant.helpers import device_registry as dr, floor_registry as fr
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import (
    STATUS_SENTINEL_TEXT,
    _active_floor_conditions,
    _active_house_conditions,
    _active_room_conditions,
    _resolve_status_text,
)
from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
    DEFAULT_DEVICE_NAME,
    DEFAULT_SCHEDULE_ID,
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
            RoomFlowHouseStatusSensor(hass, entry),
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

    hass.data[DOMAIN].setdefault("floor_status_entities", {})

    def _refresh_floor_status_sensors() -> None:
        # Floors are HA's own registry, not part of RoomFlow's config - the
        # set of floor sensors only needs to change when a floor is
        # added/removed/renamed in Settings, not on every RoomFlow config
        # save, but running this from the same refresh points a config
        # save already triggers (see ws_save_config) costs nothing and
        # catches "a floor_condition now references a floor with no
        # sensor yet" for free.
        floors = fr.async_get(hass).async_list_floors()
        existing = hass.data[DOMAIN]["floor_status_entities"]
        current_floor_ids = {floor.floor_id for floor in floors}

        for floor_id in list(existing):
            if floor_id not in current_floor_ids:
                entity = existing.pop(floor_id)
                hass.async_create_task(entity.async_remove(force_remove=True))

        new_entities = []
        for floor in floors:
            if floor.floor_id not in existing:
                entity = RoomFlowFloorStatusSensor(hass, entry, floor.floor_id)
                existing[floor.floor_id] = entity
                new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

        # Best-effort: keep an already-existing floor sensor's device name
        # in sync if the floor itself was renamed in Settings.
        device_registry = dr.async_get(hass)
        for floor in floors:
            if floor.floor_id not in existing:
                continue
            device = device_registry.async_get_device(identifiers={(DOMAIN, f"floor_{floor.floor_id}")})
            if device:
                device_registry.async_update_device(device.id, name=floor.name)

    hass.data[DOMAIN]["refresh_floor_sensors_fn"] = _refresh_floor_status_sensors
    _refresh_floor_status_sensors()


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
        forced = self.hass.data.get(DOMAIN, {}).get("forced_period", {}).get(self._schedule_id)
        if forced is not None:
            period_id = forced
        else:
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

        cfg = self.hass.data.get(DOMAIN, {}).get("config", {})
        domain_data = self.hass.data.get(DOMAIN, {})
        get_period_fn = domain_data.get("get_period_fn")
        get_day_type_fn = domain_data.get("get_day_type_fn")
        get_home_state_fn = domain_data.get("get_home_state_fn")
        period = get_period_fn(room.get("schedule_id")) if get_period_fn else None
        day_type = get_day_type_fn() if get_day_type_fn else "weekday"
        home_state = get_home_state_fn() if get_home_state_fn else "home"

        conditions = room.get("custom_conditions", [])
        active_ids = _active_room_conditions(self.hass, room, cfg)
        status = _resolve_status_text(cfg, active_ids, period, day_type, home_state, room)
        status = STATUS_SENTINEL_TEXT.get(status, status)

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


class RoomFlowFloorStatusSensor(SensorEntity):
    """A floor's current status: the name of whichever floor-level
    condition is active (cfg.floor_conditions scoped to this floor_id),
    else an active house-wide condition, else "Away"/"Weekend"/the
    current period - the middle tier of the same room -> floor -> house
    cascade RoomFlowRoomStatusSensor and RoomFlowHouseStatusSensor cover
    (mirrors the old per-floor "Övervåning/Undervåning status" template
    sensors). Lives in its own device named after the floor - there's no
    HA "floor device" to attach to, unlike a room status sensor's area.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, floor_id: str) -> None:
        self.hass = hass
        self._entry = entry
        self._floor_id = floor_id
        self._attr_unique_id = f"{entry.entry_id}_floor_{floor_id}_status"
        self._attr_name = "Status"
        self._attr_icon = "mdi:home-floor-g"
        self._refresh_device_info()

    def _floor_name(self) -> str:
        floor = fr.async_get(self.hass).async_get_floor(self._floor_id)
        return floor.name if floor else "Floor"

    def _refresh_device_info(self) -> None:
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"floor_{self._floor_id}")},
            name=self._floor_name(),
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
        cfg = self.hass.data.get(DOMAIN, {}).get("config", {})
        domain_data = self.hass.data.get(DOMAIN, {})
        get_period_fn = domain_data.get("get_period_fn")
        get_day_type_fn = domain_data.get("get_day_type_fn")
        get_home_state_fn = domain_data.get("get_home_state_fn")
        period = get_period_fn(DEFAULT_SCHEDULE_ID) if get_period_fn else None
        day_type = get_day_type_fn() if get_day_type_fn else "weekday"
        home_state = get_home_state_fn() if get_home_state_fn else "home"

        floor_conditions = [c for c in cfg.get("floor_conditions", []) if c.get("floor_id") == self._floor_id]
        active_ids = _active_floor_conditions(self.hass, cfg, self._floor_id)
        active_ids = active_ids + _active_house_conditions(self.hass, cfg)
        status = _resolve_status_text(cfg, active_ids, period, day_type, home_state)
        status = STATUS_SENTINEL_TEXT.get(status, status)

        active_id_set = set(active_ids)
        attributes: dict[str, bool] = {}
        used_keys: set[str] = set()
        for condition in floor_conditions:
            name = condition.get("name")
            if not name:
                continue
            key = _slugify(name, used_keys)
            used_keys.add(key)
            attributes[key] = condition.get("id") in active_id_set

        self._attr_native_value = status
        self._attr_extra_state_attributes = attributes


class RoomFlowHouseStatusSensor(_RoomFlowBaseSensor):
    """The whole house's current status: the name of whichever house-wide
    condition is active (cfg.house_conditions), else "Away"/"Weekend"/the
    current period - the top tier of the same room -> floor -> house
    cascade RoomFlowRoomStatusSensor and RoomFlowFloorStatusSensor cover
    (mirrors the old "Hus status" template sensor). Lives in the shared
    RoomFlow device, like Day type/Home state, since there's exactly one
    of these."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, key="house_status", name="House status", icon="mdi:home-city-outline")

    def _update_state(self) -> None:
        cfg = self.hass.data.get(DOMAIN, {}).get("config", {})
        domain_data = self.hass.data.get(DOMAIN, {})
        get_period_fn = domain_data.get("get_period_fn")
        get_day_type_fn = domain_data.get("get_day_type_fn")
        get_home_state_fn = domain_data.get("get_home_state_fn")
        period = get_period_fn(DEFAULT_SCHEDULE_ID) if get_period_fn else None
        day_type = get_day_type_fn() if get_day_type_fn else "weekday"
        home_state = get_home_state_fn() if get_home_state_fn else "home"

        conditions = cfg.get("house_conditions", [])
        active_ids = _active_house_conditions(self.hass, cfg)
        status = _resolve_status_text(cfg, active_ids, period, day_type, home_state)
        status = STATUS_SENTINEL_TEXT.get(status, status)

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
