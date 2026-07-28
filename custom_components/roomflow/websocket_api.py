"""Websocket commands used by the RoomFlow card."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er

from .const import DOMAIN


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
    areas = [{"area_id": a.id, "name": a.name} for a in registry.async_list_areas()]
    connection.send_result(msg["id"], areas)


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


def async_register_commands(hass: HomeAssistant) -> None:
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_save_config)
    websocket_api.async_register_command(hass, ws_apply_now)
    websocket_api.async_register_command(hass, ws_apply_room)
    websocket_api.async_register_command(hass, ws_list_areas)
    websocket_api.async_register_command(hass, ws_list_entities)
