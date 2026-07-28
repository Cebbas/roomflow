"""RoomFlow per-period binary sensor entities.

These are OUTPUTS: one binary_sensor per period (a user-editable,
priority-ordered list - see const.py's infer_periods), "on" exactly when
that period is the currently resolved one, regardless of which source
determined it. Not to be confused with a "boolean"-sourced period's own
config, which is an INPUT: an existing entity you point a specific period
at, as one of several ways that period can determine it's currently active.

Periods can be added/removed/renamed at any time from the card, with no
integration reload - so these entities are created/removed dynamically,
mirroring the exact pattern already used for per-room status sensors in
sensor.py (_refresh_room_status_sensors/refresh_rooms_fn).
"""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_DEVICE_NAME,
    DEFAULT_DEVICE_NAME,
    SIGNAL_RECOMPUTE,
    infer_periods,
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
        periods = infer_periods(cfg)
        existing = hass.data[DOMAIN]["period_entities"]
        current_period_ids = {period["id"] for period in periods}

        for period_id in list(existing):
            if period_id not in current_period_ids:
                entity = existing.pop(period_id)
                hass.async_create_task(entity.async_remove(force_remove=True))

        new_entities = []
        for period in periods:
            if period["id"] not in existing:
                entity = RoomFlowPeriodBooleanSensor(hass, entry, period["id"])
                existing[period["id"]] = entity
                new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    hass.data[DOMAIN]["refresh_periods_fn"] = _refresh_period_sensors
    _refresh_period_sensors()


class RoomFlowPeriodBooleanSensor(BinarySensorEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, period_id: str) -> None:
        self.hass = hass
        self._period_id = period_id
        self._attr_unique_id = f"{entry.entry_id}_is_{period_id}"
        self._attr_icon = _PERIOD_ICONS.get(period_id, _DEFAULT_PERIOD_ICON)
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
        domain_data = self.hass.data.get(DOMAIN, {})
        cfg = domain_data.get("config", {})
        period = next((p for p in infer_periods(cfg) if p.get("id") == self._period_id), None)
        # Keep the display name in sync with the period's current name
        # (renamed via the card) - picked up on the next state write.
        self._attr_name = period.get("name", self._period_id) if period else self._period_id

        get_period_fn = domain_data.get("get_period_fn")
        self._attr_is_on = get_period_fn() == self._period_id if get_period_fn else False
