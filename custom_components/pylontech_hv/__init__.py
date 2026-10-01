"""Support for Pylontech HV BMS."""

from __future__ import annotations

import logging
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN, KEY_COORDINATOR, PLATFORMS
from .coordinator import PylontechUpdateCoordinator
from .pylontech import PylontechBMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Pylontech HV BMS from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    pylontech: PylontechBMS | None = None

    try:
        _LOGGER.debug("Connecting to Pylontech BMS at %s:%s", host, port)
        pylontech = PylontechBMS(host, port)
        await pylontech.connect()
        info = await pylontech.info()
    except Exception as err:
        _LOGGER.exception("Failed to connect to Pylontech BMS at %s:%s", host, port)
        raise ConfigEntryNotReady from err
    finally:
        if pylontech is not None:
            try:
                await pylontech.disconnect()
            except Exception:
                _LOGGER.debug("Error while disconnecting", exc_info=True)

    # Preserve stable BMU numbering across reloads.
    pattern = re.compile(r"BMU #(\d+)")
    device_registry = dr.async_get(hass)
    bmu_serials: dict[str, int] = {}

    for device in device_registry.devices.get_devices_for_config_entry_id(entry.entry_id):
        if not device.name or "BMU #" not in device.name or not device.serial_number:
            continue
        match = pattern.search(device.name)
        if match:
            bmu_serials[device.serial_number] = int(match.group(1))

    new_idx = max(bmu_serials.values(), default=-1) + 1
    for serial in info.bmu_modules:
        if serial not in bmu_serials:
            bmu_serials[serial] = new_idx
            new_idx += 1

    coordinator = PylontechUpdateCoordinator(
        hass=hass,
        entry=entry,
        pylontech=pylontech,
        info=info,
        bmu_serials=bmu_serials,
    )

    try:
        await coordinator.detect_sensors()
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.exception("Failed to initialize Pylontech sensors")
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = {KEY_COORDINATOR: coordinator}

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
