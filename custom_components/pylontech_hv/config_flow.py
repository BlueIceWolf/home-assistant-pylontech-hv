"""Config and options flow for Pylontech HV BMS."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CELL_ENTITIES_FULL,
    CELL_ENTITIES_NONE,
    CELL_ENTITIES_VOLTAGE,
    CONF_CELL_ENTITIES,
    CONF_CELL_SCAN_INTERVAL,
    CONF_MODULE_DETAILS,
    CONF_EXTERNAL_POWER_ENTITY,
    CONF_EXTERNAL_POWER_INVERT,
    DEFAULT_EXTERNAL_POWER_INVERT,
    CONF_SCAN_INTERVAL,
    CONF_WARN_CELL_DELTA_MV,
    CONF_WARN_MAX_CELL_TEMP,
    CONF_WARN_MAX_CELL_VOLTAGE,
    CONF_WARN_MIN_CELL_VOLTAGE,
    DEFAULT_CELL_ENTITIES,
    DEFAULT_CELL_SCAN_INTERVAL,
    DEFAULT_MODULE_DETAILS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WARN_CELL_DELTA_MV,
    DEFAULT_WARN_MAX_CELL_TEMP,
    DEFAULT_WARN_MAX_CELL_VOLTAGE,
    DEFAULT_WARN_MIN_CELL_VOLTAGE,
    DOMAIN,
)
from .pylontech import PylontechBMS


class PylontechHVConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the Pylontech HV config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Configure a Pylontech HV BMS."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            bms: PylontechBMS | None = None
            try:
                bms = PylontechBMS(host, port)
                await bms.connect()
                info = await bms.info()
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                unique_id = info.module_barcode.value or f"{host}:{port}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=DEFAULT_NAME,
                    data={CONF_HOST: host, CONF_PORT: port},
                )
            finally:
                if bms is not None:
                    try:
                        await bms.disconnect()
                    except Exception:
                        pass

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> PylontechHVOptionsFlow:
        """Return options flow."""
        return PylontechHVOptionsFlow(config_entry)


class PylontechHVOptionsFlow(config_entries.OptionsFlow):
    """Configure Pylontech HV options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage integration options."""
        if user_input is not None:
            # Do not allow cell polling faster than normal polling.
            if user_input[CONF_CELL_SCAN_INTERVAL] < user_input[CONF_SCAN_INTERVAL]:
                user_input[CONF_CELL_SCAN_INTERVAL] = user_input[CONF_SCAN_INTERVAL]
            return self.async_create_entry(title="", data=user_input)

        o = self._entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=o.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                vol.Required(
                    CONF_CELL_SCAN_INTERVAL,
                    default=o.get(
                        CONF_CELL_SCAN_INTERVAL, DEFAULT_CELL_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
                vol.Required(
                    CONF_CELL_ENTITIES,
                    default=o.get(CONF_CELL_ENTITIES, DEFAULT_CELL_ENTITIES),
                ): vol.In(
                    [
                        CELL_ENTITIES_NONE,
                        CELL_ENTITIES_VOLTAGE,
                        CELL_ENTITIES_FULL,
                    ]
                ),
                vol.Required(
                    CONF_MODULE_DETAILS,
                    default=o.get(CONF_MODULE_DETAILS, DEFAULT_MODULE_DETAILS),
                ): bool,
                vol.Optional(
                    CONF_EXTERNAL_POWER_ENTITY,
                    description={"suggested_value": o.get(CONF_EXTERNAL_POWER_ENTITY)},
                ): EntitySelector(EntitySelectorConfig(domain="sensor")),
                vol.Required(
                    CONF_EXTERNAL_POWER_INVERT,
                    default=o.get(CONF_EXTERNAL_POWER_INVERT, DEFAULT_EXTERNAL_POWER_INVERT),
                ): bool,
                vol.Required(
                    CONF_WARN_CELL_DELTA_MV,
                    default=o.get(
                        CONF_WARN_CELL_DELTA_MV, DEFAULT_WARN_CELL_DELTA_MV
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=500)),
                vol.Required(
                    CONF_WARN_MAX_CELL_TEMP,
                    default=o.get(
                        CONF_WARN_MAX_CELL_TEMP, DEFAULT_WARN_MAX_CELL_TEMP
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=20, max=80)),
                vol.Required(
                    CONF_WARN_MIN_CELL_VOLTAGE,
                    default=o.get(
                        CONF_WARN_MIN_CELL_VOLTAGE, DEFAULT_WARN_MIN_CELL_VOLTAGE
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=2.0, max=4.0)),
                vol.Required(
                    CONF_WARN_MAX_CELL_VOLTAGE,
                    default=o.get(
                        CONF_WARN_MAX_CELL_VOLTAGE, DEFAULT_WARN_MAX_CELL_VOLTAGE
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=2.5, max=4.5)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
