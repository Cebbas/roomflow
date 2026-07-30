"""Diagnostics support for RoomFlow.

Deliberately avoids including device entity_ids for rooms (counts/structure
only), since diagnostics are often attached to public bug reports.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN,
    CONF_TIME_SENSOR,
    CONF_DAY_TYPE_SENSOR,
    CONF_DAY_TYPE_SENSOR_INVERTED,
    CONF_HOME_SENSOR,
    CONF_PERIOD_MAP,
    CONF_ILLUMINANCE_SENSOR,
    CONF_PERIOD_BOOLEANS,
    CONF_PERSON_ENTITIES,
    infer_time_sources,
    infer_day_type_mode,
    infer_home_mode,
)


def _state_snapshot(hass: HomeAssistant, entity_id: str | None) -> dict | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None:
        return {"entity_id": entity_id, "state": None}
    return {"entity_id": entity_id, "state": state.state}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    domain_data = hass.data.get(DOMAIN, {})
    config = domain_data.get("config", {})

    time_sensor = config.get(CONF_TIME_SENSOR)
    day_type_sensor = config.get(CONF_DAY_TYPE_SENSOR)
    home_sensor = config.get(CONF_HOME_SENSOR)
    illuminance_sensor = config.get(CONF_ILLUMINANCE_SENSOR)
    period_booleans = config.get(CONF_PERIOD_BOOLEANS, {})
    person_entities = config.get(CONF_PERSON_ENTITIES, [])

    return {
        "time_sources": infer_time_sources(config),
        "day_type_mode": infer_day_type_mode(config),
        "day_type_sensor_inverted": config.get(CONF_DAY_TYPE_SENSOR_INVERTED, False),
        "home_mode": infer_home_mode(config),
        "period_map": config.get(CONF_PERIOD_MAP),
        "sensor_states": {
            "time_sensor": _state_snapshot(hass, time_sensor),
            "day_type_sensor": _state_snapshot(hass, day_type_sensor),
            "home_sensor": _state_snapshot(hass, home_sensor),
            "illuminance_sensor": _state_snapshot(hass, illuminance_sensor),
            "period_booleans": {
                period: _state_snapshot(hass, entity_id)
                for period, entity_id in period_booleans.items()
            },
            "person_entities": [_state_snapshot(hass, e) for e in person_entities],
        },
        "room_count": len(config.get("rooms", [])),
        "button_trigger_count": len(config.get("button_triggers", [])),
        "default_transitions": config.get("default_transitions"),
        "motion_sensors": [
            {
                "name": m.get("name"),
                "trigger_count": len(m.get("triggers", [])),
                "trigger_types": [t.get("type") for t in m.get("triggers", [])],
                "timeout_minutes": m.get("timeout_minutes"),
                "warn_enabled": m.get("warn_enabled", False),
                "warn_minutes": m.get("warn_minutes"),
                "warn_brightness": m.get("warn_brightness"),
            }
            for m in config.get("motion_sensors", [])
        ],
        "button_triggers": [
            {"name": t.get("name"), "click_type": t.get("click_type", "any")}
            for t in config.get("button_triggers", [])
        ],
        "rooms": [
            {
                "name": room.get("name"),
                "device_count": len(room.get("devices", [])),
                "device_types": [d.get("type") for d in room.get("devices", [])],
                "motion_controlled_device_count": sum(
                    1
                    for d in room.get("devices", [])
                    if any(p.get("mode") == "motion" for p in (d.get("control") or {}).values())
                ),
                "custom_condition_count": len(room.get("custom_conditions", [])),
                "room_button_attachments": [
                    {"action": b.get("action"), "force_period": b.get("force_period")}
                    for b in room.get("buttons", [])
                ],
                "device_button_attachment_count": sum(
                    len(d.get("buttons", [])) for d in room.get("devices", [])
                ),
            }
            for room in config.get("rooms", [])
        ],
    }
