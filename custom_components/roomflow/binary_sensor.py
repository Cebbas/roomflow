"""RoomFlow per-period binary sensor entities.

These are OUTPUTS: one binary_sensor per (schedule, period) pair - see
const.py's infer_schedules - "on" exactly when that period is the
currently resolved one for its own schedule, regardless of which
condition determined it. Not to be confused with a "state"-type
condition's own entity_id, which is an INPUT: an existing entity a
condition compares against, as one of several ways a period can resolve
active.

Each schedule gets its own device (like a room's own status sensor
device in sensor.py), grouping that schedule's period sensors together
and letting two different schedules both have a period called e.g.
"morning" without name collisions.

Schedules/periods can be added/removed/renamed at any time from the
card, with no integration reload - so these entities are created/removed
dynamically, mirroring the exact pattern already used for per-room status
sensors in sensor.py (_refresh_room_status_sensors/refresh_rooms_fn).
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    SIGNAL_RECOMPUTE,
    infer_schedules,
)

# Nice icons for the 5 built-in default periods (their id *is* the literal
# name below); any user-added period id not in this dict gets the generic
# fallback, since there's no way to guess an icon for an arbitrary new name.
_PERIOD_ICONS = {
    "morning": "mdi:weather-sunset-up",
    "day": "mdi:white-balance-sunny",
    "afternoon": "mdi:weather-sunny",
    "evening": "mdi:weather-sunset-down",
    "night": "mdi:weather-night",
}
_DEFAULT_PERIOD_ICON = "mdi:clock-outline"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hass.data[DOMAIN].setdefault("period_entities", {})

    def _refresh_period_sensors() -> None:
        cfg = hass.data[DOMAIN]["config"]
        schedules = infer_schedules(cfg)
        existing = hass.data[DOMAIN]["period_entities"]
        current_keys = {(s["id"], p["id"]) for s in schedules for p in s["periods"]}

        for key in list(existing):
            if key not in current_keys:
                entity = existing.pop(key)
                hass.async_create_task(entity.async_remove(force_remove=True))

        new_entities = []
        for schedule in schedules:
            for period in schedule["periods"]:
                key = (schedule["id"], period["id"])
                if key not in existing:
                    entity = RoomFlowPeriodBooleanSensor(hass, entry, schedule["id"], period["id"])
                    existing[key] = entity
                    new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

        # Best-effort: keep each already-existing schedule device's name in
        # sync (renamed via the card) - a brand-new entity's device already
        # gets the right name at creation time via its own DeviceInfo, same
        # pattern as _refresh_room_status_sensors in sensor.py.
        device_registry = dr.async_get(hass)
        for schedule in schedules:
            if not any(key[0] == schedule["id"] for key in existing):
                continue
            device = device_registry.async_get_device(identifiers={(DOMAIN, f"schedule_{schedule['id']}")})
            if device:
                device_registry.async_update_device(device.id, name=schedule.get("name"))

    hass.data[DOMAIN]["refresh_periods_fn"] = _refresh_period_sensors
    _refresh_period_sensors()


class RoomFlowPeriodBooleanSensor(BinarySensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, schedule_id: str, period_id: str) -> None:
        self.hass = hass
        self._schedule_id = schedule_id
        self._period_id = period_id
        self._attr_unique_id = f"{entry.entry_id}_{schedule_id}_is_{period_id}"
        self._attr_icon = _PERIOD_ICONS.get(period_id, _DEFAULT_PERIOD_ICON)
        schedule = self._schedule()
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"schedule_{schedule_id}")},
            name=schedule.get("name") if schedule else schedule_id,
            entry_type=DeviceEntryType.SERVICE,
        )

    def _schedule(self) -> dict | None:
        cfg = self.hass.data.get(DOMAIN, {}).get("config", {})
        return next((s for s in infer_schedules(cfg) if s["id"] == self._schedule_id), None)

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
        domain_data = self.hass.data.get(DOMAIN, {})
        schedule = self._schedule()
        period = next((p for p in (schedule["periods"] if schedule else []) if p.get("id") == self._period_id), None)
        # Keep the display name in sync with the period's current name
        # (renamed via the card) - picked up on the next state write.
        self._attr_name = period.get("name", self._period_id) if period else self._period_id

        get_period_fn = domain_data.get("get_period_fn")
        self._attr_is_on = (
            get_period_fn(self._schedule_id) == self._period_id if get_period_fn else False
        )
