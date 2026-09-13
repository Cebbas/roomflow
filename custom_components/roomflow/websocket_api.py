"""Websocket commands used by the RoomFlow card."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    floor_registry as fr,
)

from . import (
    _active_floor_conditions,
    _active_house_conditions,
    _active_room_conditions,
    _resolve_status_text,
)
from .const import DOMAIN, DEFAULT_SCHEDULE_ID, infer_schedules


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_config"})
@websocket_api.async_response
async def ws_get_config(hass: HomeAssistant, connection, msg):
    data = hass.data[DOMAIN]["config"]
    connection.send_result(msg["id"], data)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/save_config",
        vol.Required("config"): dict,
    }
)
@websocket_api.async_response
async def ws_save_config(hass: HomeAssistant, connection, msg):
    hass.data[DOMAIN]["config"] = msg["config"]
    await hass.data[DOMAIN]["store"].async_save(msg["config"])

    # Refresh button/motion/time-source listeners and the device name/area
    # so newly added/removed/changed settings take effect immediately -
    # no integration reload needed
    for refresh_key in (
        "refresh_buttons_fn",
        "refresh_motion_fn",
        "refresh_time_fn",
        "refresh_device_fn",
        "refresh_rooms_fn",
        "refresh_periods_fn",
        "refresh_schedule_sensors_fn",
        "refresh_floor_sensors_fn",
    ):
        refresh_fn = hass.data[DOMAIN].get(refresh_key)
        if refresh_fn:
            refresh_fn()

    # Apply immediately so changes are visible without waiting for the next
    # period change
    apply_fn = hass.data[DOMAIN].get("apply_fn")
    if apply_fn:
        await apply_fn()
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/apply_now"})
@websocket_api.async_response
async def ws_apply_now(hass: HomeAssistant, connection, msg):
    apply_fn = hass.data[DOMAIN].get("apply_fn")
    if apply_fn:
        await apply_fn()
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/apply_room",
        vol.Required("room_id"): str,
    }
)
@websocket_api.async_response
async def ws_apply_room(hass: HomeAssistant, connection, msg):
    apply_room_fn = hass.data[DOMAIN].get("apply_room_fn")
    if apply_room_fn:
        await apply_room_fn(msg["room_id"])
    connection.send_result(msg["id"], {"ok": True})


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/list_areas"})
@websocket_api.async_response
async def ws_list_areas(hass: HomeAssistant, connection, msg):
    registry = ar.async_get(hass)
    areas = [
        {"area_id": a.id, "name": a.name, "icon": a.icon, "floor_id": a.floor_id}
        for a in registry.async_list_areas()
    ]
    connection.send_result(msg["id"], areas)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/list_floors"})
@websocket_api.async_response
async def ws_list_floors(hass: HomeAssistant, connection, msg):
    registry = fr.async_get(hass)
    floors = [
        {"floor_id": f.floor_id, "name": f.name, "icon": f.icon, "level": f.level}
        for f in registry.async_list_floors()
    ]
    connection.send_result(msg["id"], floors)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/list_entities"})
@websocket_api.async_response
async def ws_list_entities(hass: HomeAssistant, connection, msg):
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    result = []
    for state in hass.states.async_all():
        domain = state.entity_id.split(".")[0]
        if domain not in ("light", "switch"):
            continue
        entry = entity_registry.async_get(state.entity_id)

        # Most entities get their area from the device they belong to
        # (set via "Settings -> Devices" on the device, not the entity) -
        # only fall back to that when the entity has no area of its own.
        area_id = None
        if entry:
            area_id = entry.area_id
            if area_id is None and entry.device_id:
                device = device_registry.async_get(entry.device_id)
                if device:
                    area_id = device.area_id

        supported_color_modes = (
            state.attributes.get("supported_color_modes", []) if domain == "light" else []
        )
        supports_brightness = any(m != "onoff" for m in supported_color_modes)
        supports_color_temp = "color_temp" in supported_color_modes

        result.append(
            {
                "entity_id": state.entity_id,
                "name": state.attributes.get("friendly_name", state.entity_id),
                "domain": domain,
                "area_id": area_id,
                "supports_brightness": supports_brightness,
                "supports_color_temp": supports_color_temp,
            }
        )
    connection.send_result(msg["id"], result)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/get_dashboard"})
@websocket_api.async_response
async def ws_get_dashboard(hass: HomeAssistant, connection, msg):
    """Overview tab data: each schedule's currently resolved period (forced
    override wins if one is active, same precedence the sensors use - see
    sensor.py/binary_sensor.py), plus the persisted logs, newest first."""
    domain_data = hass.data[DOMAIN]
    cfg = domain_data["config"]
    get_period_fn = domain_data.get("get_period_fn")
    forced = domain_data.get("forced_period", {})

    schedules = []
    for schedule in infer_schedules(cfg):
        schedule_id = schedule["id"]
        period_id = forced.get(schedule_id) or (get_period_fn(schedule_id) if get_period_fn else None)
        period = next((p for p in schedule["periods"] if p["id"] == period_id), None)
        schedules.append(
            {
                "id": schedule_id,
                "name": schedule.get("name", schedule_id),
                "period_id": period_id,
                "period_name": period.get("name", period_id) if period else period_id,
            }
        )

    get_day_type_fn = domain_data.get("get_day_type_fn")
    get_home_state_fn = domain_data.get("get_home_state_fn")
    day_type = get_day_type_fn() if get_day_type_fn else "weekday"
    home_state = get_home_state_fn() if get_home_state_fn else "home"
    # House/floor status has no one room's schedule to follow - same as
    # the House/Floor status sensors (sensor.py), it reads the default
    # schedule's period as its own time-of-day fallback.
    house_period_id = forced.get(DEFAULT_SCHEDULE_ID) or (
        get_period_fn(DEFAULT_SCHEDULE_ID) if get_period_fn else None
    )
    default_schedule = next(
        (s for s in infer_schedules(cfg) if s["id"] == DEFAULT_SCHEDULE_ID), None
    )
    house_period_name = None
    if default_schedule:
        house_period = next(
            (p for p in default_schedule["periods"] if p["id"] == house_period_id), None
        )
        house_period_name = house_period.get("name", house_period_id) if house_period else house_period_id

    house_active_ids = _active_house_conditions(hass, cfg)
    house_status = _resolve_status_text(cfg, house_active_ids, house_period_name, day_type, home_state)

    floors = []
    for floor in fr.async_get(hass).async_list_floors():
        floor_active_ids = _active_floor_conditions(hass, cfg, floor.floor_id) + house_active_ids
        floors.append(
            {
                "floor_id": floor.floor_id,
                "name": floor.name,
                "status": _resolve_status_text(cfg, floor_active_ids, house_period_name, day_type, home_state),
            }
        )

    motion_off_timers = domain_data.get("motion_off_timers", {})

    rooms = []
    for room in cfg.get("rooms", []):
        room_schedule_id = room.get("schedule_id") or DEFAULT_SCHEDULE_ID
        room_period_id = forced.get(room_schedule_id) or (
            get_period_fn(room_schedule_id) if get_period_fn else None
        )
        room_schedule = next((s for s in schedules if s["id"] == room_schedule_id), None)
        room_period_name = (
            room_schedule["period_name"]
            if room_schedule and room_schedule["period_id"] == room_period_id
            else room_period_id
        )
        room_active_ids = _active_room_conditions(hass, room, cfg)
        # Any device currently counting down to a motion-triggered dim/off
        # (see _schedule_motion_off in __init__.py) - lets the Overview
        # tab show a live countdown under the room instead of just the
        # motion sensor's raw on/off state. The key format (f"{room_id}:
        # {entity_id}") is duplicated rather than imported since it's a
        # closure local to async_setup_entry there.
        motion_timers = []
        for device in room.get("devices", []):
            entry = motion_off_timers.get(f"{room['id']}:{device['entity_id']}")
            if entry:
                motion_timers.append(
                    {
                        "entity_id": device["entity_id"],
                        "name": device.get("name", device["entity_id"]),
                        "next_action": entry["next_action"],
                        "fires_at": entry["fires_at"].isoformat(),
                    }
                )
        rooms.append(
            {
                "room_id": room["id"],
                "status": _resolve_status_text(cfg, room_active_ids, room_period_name, day_type, home_state, room),
                "motion_timers": motion_timers,
            }
        )

    connection.send_result(
        msg["id"],
        {
            "schedules": schedules,
            "device_log": list(reversed(domain_data.get("device_log", []))),
            "period_log": list(reversed(domain_data.get("period_log", []))),
            "button_log": list(reversed(domain_data.get("button_log", []))),
            "house_status": house_status,
            "floor_status": floors,
            "room_status": rooms,
        },
    )


def async_register_commands(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_save_config)
    websocket_api.async_register_command(hass, ws_apply_now)
    websocket_api.async_register_command(hass, ws_apply_room)
    websocket_api.async_register_command(hass, ws_list_areas)
    websocket_api.async_register_command(hass, ws_list_floors)
    websocket_api.async_register_command(hass, ws_list_entities)
    websocket_api.async_register_command(hass, ws_get_dashboard)
