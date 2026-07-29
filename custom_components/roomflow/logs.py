"""Persisted logs of RoomFlow's own actions - device changes it applies and
period transitions - surfaced in the card's Overview tab. Kept in a
separate Store from the main config (STORAGE_KEY in const.py) since these
are high-churn, append-only event lists rather than user-edited settings,
and capped at MAX_LOG_ENTRIES each so the stored file can't grow forever.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

STORAGE_KEY_LOGS = "roomflow_logs"
STORAGE_VERSION_LOGS = 1
MAX_LOG_ENTRIES = 200


async def async_load_logs(hass: HomeAssistant) -> None:
    store: Store = Store(hass, STORAGE_VERSION_LOGS, STORAGE_KEY_LOGS)
    data = await store.async_load() or {}
    hass.data[DOMAIN]["log_store"] = store
    hass.data[DOMAIN]["device_log"] = data.get("device_log", [])
    hass.data[DOMAIN]["period_log"] = data.get("period_log", [])


def _persist(hass: HomeAssistant) -> None:
    store: Store = hass.data[DOMAIN]["log_store"]
    store.async_delay_save(
        lambda: {
            "device_log": hass.data[DOMAIN]["device_log"],
            "period_log": hass.data[DOMAIN]["period_log"],
        },
        5,
    )


def log_device_change(
    hass: HomeAssistant,
    *,
    room_id: str | None,
    room_name: str,
    entity_id: str,
    device_name: str,
    state_label: str,
    period_name: str,
    source: str,
) -> None:
    """Record one device state change RoomFlow itself just applied."""
    entries = hass.data[DOMAIN]["device_log"]
    entries.append(
        {
            "time": dt_util.now().isoformat(),
            "room_id": room_id,
            "room_name": room_name,
            "entity_id": entity_id,
            "device_name": device_name,
            "state_label": state_label,
            "period_name": period_name,
            "source": source,
        }
    )
    del entries[: max(0, len(entries) - MAX_LOG_ENTRIES)]
    _persist(hass)


def log_period_change(
    hass: HomeAssistant,
    *,
    schedule_id: str,
    schedule_name: str,
    period_id: str,
    period_name: str,
    source: str,
) -> None:
    """Record a schedule's resolved period actually changing (not every
    recompute tick - callers only call this once the value differs from
    what was last logged)."""
    entries = hass.data[DOMAIN]["period_log"]
    entries.append(
        {
            "time": dt_util.now().isoformat(),
            "schedule_id": schedule_id,
            "schedule_name": schedule_name,
            "period_id": period_id,
            "period_name": period_name,
            "source": source,
        }
    )
    del entries[: max(0, len(entries) - MAX_LOG_ENTRIES)]
    _persist(hass)
