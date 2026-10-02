"""Warning binary sensors for Pylontech HV BMS."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, KEY_COORDINATOR
from .coordinator import PylontechUpdateCoordinator


WARNINGS = {
    "warn_any": "BMS Warnung",
    "warn_cell_imbalance": "Zellabweichung",
    "warn_temperature": "Temperaturwarnung",
    "warn_cell_voltage": "Zellspannungswarnung",
    "warn_bms_state": "BMS Statuswarnung",
    "balance_recommended": "Ausgleichsladung empfohlen",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PylontechUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        KEY_COORDINATOR
    ]
    async_add_entities(
        PylontechWarningSensor(coordinator, key, name)
        for key, name in WARNINGS.items()
    )


class PylontechWarningSensor(
    CoordinatorEntity[PylontechUpdateCoordinator],
    BinarySensorEntity,
):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: PylontechUpdateCoordinator,
        sensor_id: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_id = sensor_id
        self._attr_name = name
        self._attr_unique_id = f"{sensor_id}-{coordinator.serial_nr}"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.sensor_value(self._sensor_id))

    @property
    def extra_state_attributes(self):
        if self._sensor_id != "warn_any":
            return None
        return {
            "meldung": self.coordinator.sensor_value("warn_message"),
            "zell_delta_v": self.coordinator.sensor_value("diag_cell_delta_v"),
            "temperatur_delta_k": self.coordinator.sensor_value("diag_temp_delta_k"),
            "fehlercode": self.coordinator.sensor_value("error_code"),
        }
