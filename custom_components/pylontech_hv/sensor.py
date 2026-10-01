"""Sensors for Pylontech HV BMS."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CELL_ENTITIES_FULL,
    CELL_ENTITIES_NONE,
    CONF_CELL_ENTITIES,
    CONF_MODULE_DETAILS,
    DEFAULT_CELL_ENTITIES,
    DEFAULT_MODULE_DETAILS,
    DOMAIN,
    KEY_COORDINATOR,
)
from .coordinator import PylontechUpdateCoordinator


_DESCRIPTIONS: dict[str, SensorEntityDescription] = {
    "A": SensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    "V": SensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=3,
    ),
    "Ah": SensorEntityDescription(
        key="charge",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Ah",
    ),
    "Wh": SensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY_STORAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfEnergy.WATT_HOUR,
    ),
    "C": SensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    "%": SensorEntityDescription(
        key="battery",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
    " ": SensorEntityDescription(key="text"),
}
DIAG_SENSOR = SensorEntityDescription(key="diagnostic")

BASIC_BMU_SENSOR_IDS = {
    "volt",
    "curr",
    "temp",
    "charge_ah_perc",
    "cell_temp_low",
    "cell_temp_high",
    "cell_volt_low",
    "cell_volt_high",
}

CALCULATED = {
    "diag_power_w": (
        "Leistung",
        SensorEntityDescription(
            key="diag_power_w",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
        ),
    ),
    "diag_cell_delta_v": (
        "Zellspannungsdifferenz",
        SensorEntityDescription(
            key="diag_cell_delta_v",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            suggested_display_precision=3,
        ),
    ),
    "diag_temp_delta_k": (
        "Zelltemperaturdifferenz",
        SensorEntityDescription(
            key="diag_temp_delta_k",
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="K",
            suggested_display_precision=1,
        ),
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: PylontechUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id][
        KEY_COORDINATOR
    ]
    entities: list[SensorEntity] = []

    # Main BMS values.
    for sensor_id, sensor in coordinator.sensors.items():
        entities.append(
            PylontechSensor(
                coordinator, sensor_id, sensor.name, sensor.unit, None
            )
        )

    # Calculated diagnostics.
    for sensor_id, (name, description) in CALCULATED.items():
        entities.append(
            CalculatedSensor(coordinator, sensor_id, name, description)
        )

    # BMU values.
    extended = config_entry.options.get(
        CONF_MODULE_DETAILS, DEFAULT_MODULE_DETAILS
    )
    allowed_bmu = (
        set(coordinator.unit_sensors)
        if extended
        else BASIC_BMU_SENSOR_IDS
    )

    for unit_idx in range(coordinator.get_number_of_units()):
        bmu = coordinator.get_unit_number(unit_idx)
        for sensor_id, sensor in coordinator.unit_sensors.items():
            if sensor_id not in allowed_bmu:
                continue
            entities.append(
                PylontechSensor(
                    coordinator,
                    f"{sensor_id}_bmu_{bmu}",
                    f"{sensor.name} (BMU {bmu})",
                    sensor.unit,
                    unit_idx,
                )
            )

    # Cell entities.
    cell_mode = config_entry.options.get(
        CONF_CELL_ENTITIES, DEFAULT_CELL_ENTITIES
    )
    if cell_mode != CELL_ENTITIES_NONE:
        allowed_cells = (
            set(coordinator.bat_sensors)
            if cell_mode == CELL_ENTITIES_FULL
            else {"volt"}
        )

        for idx in reversed(range(coordinator.get_number_of_units() * 15)):
            bmu_idx = idx // 15
            cell = idx % 15
            bmu = coordinator.get_unit_number(bmu_idx)

            for sensor_id, sensor in coordinator.bat_sensors.items():
                if sensor_id not in allowed_cells:
                    continue
                entities.append(
                    PylontechSensor(
                        coordinator,
                        f"{sensor_id}_cell_{bmu}_{cell}",
                        f"{sensor.name} (BMU {bmu}, Zelle {cell + 1})",
                        sensor.unit,
                        bmu_idx,
                    )
                )

    async_add_entities(entities)


class PylontechSensor(
    CoordinatorEntity[PylontechUpdateCoordinator],
    SensorEntity,
):
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: PylontechUpdateCoordinator,
        sensor_id: str,
        name: str,
        unit: str,
        bmu_idx: int | None,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_id = sensor_id
        self._attr_name = name
        self._attr_unique_id = f"{sensor_id}-{coordinator.serial_nr}"
        self._attr_device_info = (
            coordinator.device_info
            if bmu_idx is None
            else coordinator.unit_device_infos[bmu_idx]
        )
        self.entity_description = _DESCRIPTIONS.get(unit, DIAG_SENSOR)

    @property
    def native_value(self):
        return self.coordinator.sensor_value(self._sensor_id)


class CalculatedSensor(
    CoordinatorEntity[PylontechUpdateCoordinator],
    SensorEntity,
):
    _attr_has_entity_name = False

    def __init__(
        self,
        coordinator: PylontechUpdateCoordinator,
        sensor_id: str,
        name: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self._sensor_id = sensor_id
        self._attr_name = name
        self._attr_unique_id = f"{sensor_id}-{coordinator.serial_nr}"
        self._attr_device_info = coordinator.device_info
        self.entity_description = description

    @property
    def native_value(self):
        return self.coordinator.sensor_value(self._sensor_id)
