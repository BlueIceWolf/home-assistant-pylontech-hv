"""Diagnostics support for Pylontech HV BMS."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import DOMAIN, KEY_COORDINATOR

TO_REDACT = {"host"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return downloadable diagnostics."""
    coordinator = hass.data[DOMAIN][entry.entry_id][KEY_COORDINATOR]
    return {
        "entry": async_redact_data(dict(entry.data), TO_REDACT),
        "options": dict(entry.options),
        "device": {
            "serial": coordinator.serial_nr,
            "bmu_count": coordinator.get_number_of_units(),
        },
        "warnings": {
            "active": coordinator.sensor_value("warn_any"),
            "message": coordinator.sensor_value("warn_message"),
        },
        "data": dict(coordinator.data or {}),
    }
