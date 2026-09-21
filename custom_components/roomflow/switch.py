"""RoomFlow-managed condition toggle switches.

A house/floor/room condition (see __init__.py's _active_house_conditions
/_active_floor_conditions/_active_room_conditions) is just {id, name,
entity_id, state, ...} - it doesn't care what kind of entity backs it,
only that entity_id's state matches `state`. Historically every such
toggle was a hand-created input_boolean helper (Settings -> Helpers, or
raw YAML) that the household set up long before RoomFlow existed.

A condition flagged "managed": true is instead backed by an entity
RoomFlow creates and owns itself, right here - no more manual helper
setup, and (since __init__.py's condition-matching code is entity-domain
agnostic) nothing about the matching/listener logic needed to change to
support it; see _setup_time_listeners' tracked_entities collection,
which already picks up whatever entity_id a condition points at.
"""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, SIGNAL_RECOMPUTE


def _iter_managed_conditions(cfg: dict):
    """Yield (scope, scope_id, condition) for every condition currently
    flagged managed - across all three places a condition can live.

    A condition's own id is only unique within the list it lives in
    (e.g. several rooms each have their own custom_conditions entry with
    id "natt", all pointing at the same house-wide night boolean today) -
    never globally, so callers must key by (scope, scope_id, condition
    id), not by condition id alone."""
    for condition in cfg.get("house_conditions", []):
        if condition.get("managed"):
            yield "house", None, condition
    for condition in cfg.get("floor_conditions", []):
        if condition.get("managed"):
            yield "floor", condition.get("floor_id"), condition
    for room in cfg.get("rooms", []):
        for condition in room.get("custom_conditions", []):
            if condition.get("managed"):
                yield "room", room.get("id"), condition


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    hass.data[DOMAIN].setdefault("condition_switch_entities", {})

    def _refresh_condition_switches() -> None:
        cfg = hass.data[DOMAIN]["config"]
        existing = hass.data[DOMAIN]["condition_switch_entities"]
        current = {
            (scope, scope_id, condition["id"]): condition
            for scope, scope_id, condition in _iter_managed_conditions(cfg)
        }

        for key in list(existing):
            if key not in current:
                entity = existing.pop(key)
                hass.async_create_task(entity.async_remove(force_remove=True))

        new_entities = []
        for key in current:
            if key not in existing:
                scope, scope_id, condition_id = key
                entity = RoomFlowConditionSwitch(hass, entry, scope, scope_id, condition_id)
                existing[key] = entity
                new_entities.append(entity)
        if new_entities:
            async_add_entities(new_entities)

    hass.data[DOMAIN]["refresh_condition_switches_fn"] = _refresh_condition_switches
    _refresh_condition_switches()


class RoomFlowConditionSwitch(SwitchEntity, RestoreEntity):
    """The switch entity backing one managed condition.

    Grouped onto whatever device already represents its scope (the
    room's own status-sensor device, the floor's, or the integration's
    top-level device for a house-wide condition) rather than getting a
    device of its own - same identifiers sensor.py already uses for that
    scope, so it just shows up alongside the existing entities there.
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        scope: str,
        scope_id: str | None,
        condition_id: str,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._scope = scope
        self._scope_id = scope_id
        self._condition_id = condition_id
        # scope_id is None for a house-wide condition - "house" fills that
        # slot so the id string stays fully qualified without a stray
        # "None" in it. Explicitly setting entity_id (not just unique_id)
        # guarantees this exact, predictable id rather than leaving it to
        # HA's name-based slugify - the card writes this same string into
        # the condition's entity_id field at the moment it flags a
        # condition "managed", before this entity is ever created, so the
        # two must match byte for byte.
        slug = f"{scope}_{scope_id or 'house'}_{condition_id}"
        self._attr_unique_id = f"{entry.entry_id}_condition_{slug}"
        self.entity_id = f"switch.roomflow_condition_{slug}"
        self._attr_icon = "mdi:toggle-switch-outline"
        self._attr_is_on = False
        self._refresh_device_info()

    def _condition(self) -> dict | None:
        cfg = self.hass.data.get(DOMAIN, {}).get("config", {})
        if self._scope == "house":
            pool = cfg.get("house_conditions", [])
        elif self._scope == "floor":
            pool = cfg.get("floor_conditions", [])
        else:
            room = next((r for r in cfg.get("rooms", []) if r.get("id") == self._scope_id), None)
            pool = room.get("custom_conditions", []) if room else []
        return next((c for c in pool if c.get("id") == self._condition_id), None)

    def _refresh_device_info(self) -> None:
        if self._scope == "house":
            identifier = self._entry.entry_id
        elif self._scope == "floor":
            identifier = f"floor_{self._scope_id}"
        else:
            identifier = f"room_{self._scope_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, identifier)},
            entry_type=DeviceEntryType.SERVICE,
        )

    def _update_name(self) -> None:
        condition = self._condition()
        self._attr_name = condition.get("name") if condition else self._condition_id

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"
        self._update_name()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, SIGNAL_RECOMPUTE, self._handle_signal)
        )

    @callback
    def _handle_signal(self) -> None:
        # Keeps the display name in sync if the condition is renamed from
        # the card - mirrors the same pattern in binary_sensor.py/sensor.py.
        self._update_name()
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
