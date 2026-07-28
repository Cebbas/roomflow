"""Config flow for RoomFlow.

Single instance, zero fields: everything (time-of-day/day-type/home-away
sources, rooms, devices, buttons, motion, transitions) is configured from the
RoomFlow card's own Settings/rooms/buttons tabs after adding the integration
- see the card-backed JSON config store in __init__.py/websocket_api.py.
"""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN


class RoomFlowConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow, single instance only, nothing to configure here."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is not None:
            return self.async_create_entry(title="RoomFlow", data={})

        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))
