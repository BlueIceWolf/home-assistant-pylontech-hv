"""Update coordinator for Pylontech HV BMS."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util
from homeassistant.helpers.storage import Store

from .const import (
    CONF_CELL_SCAN_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_WARN_CELL_DELTA_MV,
    CONF_WARN_MAX_CELL_TEMP,
    CONF_WARN_MAX_CELL_VOLTAGE,
    CONF_WARN_MIN_CELL_VOLTAGE,
    DEFAULT_CELL_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WARN_CELL_DELTA_MV,
    DEFAULT_WARN_MAX_CELL_TEMP,
    DEFAULT_WARN_MAX_CELL_VOLTAGE,
    DEFAULT_WARN_MIN_CELL_VOLTAGE,
    DOMAIN,
)
from .pylontech import InfoCommand, PylontechBMS, Sensor

_LOGGER = logging.getLogger(__name__)
COMMAND_PAUSE = 0.5


class PylontechUpdateCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Gather and diagnose Pylontech BMS data."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        pylontech: PylontechBMS,
        info: InfoCommand,
        bmu_serials: dict[str, int],
    ) -> None:
        self.entry = entry
        self.pylontech = pylontech
        self.info = info
        self.serial_nr = info.module_barcode.value or "Pylontech-HV"
        self.device_info = _device(info)

        self.unit_device_infos: tuple[DeviceInfo, ...] = tuple(
            _unit_device(info, bmu_serials[bmu], bmu) for bmu in info.bmu_modules
        )
        self._unit_numbers = {
            idx: bmu_serials[bmu] for idx, bmu in enumerate(info.bmu_modules)
        }

        self.sensors: dict[str, Sensor] = {}
        self.unit_sensors: dict[str, Sensor] = {}
        self.bat_sensors: dict[str, Sensor] = {}
        self._last_cell_update: datetime | None = None
        self._last_full_charge: datetime | None = None
        self._storage = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.maintenance")

        scan = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            update_interval=timedelta(seconds=scan),
            update_method=self._async_update_data,
        )

    async def detect_sensors(self) -> None:
        """Detect available sensor schemas once."""
        stored = await self._storage.async_load()
        if stored and stored.get("last_full_charge"):
            try:
                self._last_full_charge = datetime.fromisoformat(stored["last_full_charge"])
            except (TypeError, ValueError):
                self._last_full_charge = None

        connected = False
        try:
            await self.pylontech.connect()
            connected = True

            pwr = await self.pylontech.pwr()
            self.sensors = pwr.get_sensors()

            await asyncio.sleep(COMMAND_PAUSE)
            unit = await self.pylontech.unit()
            if not unit.values:
                raise ValueError("No BMU data returned by 'unit'")
            self.unit_sensors = unit.values[0].get_sensors()

            await asyncio.sleep(COMMAND_PAUSE)
            bat = await self.pylontech.bat()
            if not bat.values:
                raise ValueError("No cell data returned by 'bat'")
            self.bat_sensors = bat.values[0].get_sensors()
            self._last_cell_update = dt_util.utcnow()

        finally:
            if connected:
                await self._safe_disconnect()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch BMS, BMU and optionally cell data."""
        connected = False

        try:
            result: dict[str, Any] = dict(self.data or {})
            await self.pylontech.connect()
            connected = True

            pwr = await self.pylontech.pwr()
            result.update({k: v.value for k, v in pwr.get_sensors().items()})

            await asyncio.sleep(COMMAND_PAUSE)
            unit = await self.pylontech.unit()
            for idx, unit_data in enumerate(unit.values):
                if idx not in self._unit_numbers:
                    continue
                bmu = self.get_unit_number(idx)
                result.update(
                    {
                        f"{key}_bmu_{bmu}": sensor.value
                        for key, sensor in unit_data.get_sensors().items()
                    }
                )

            if self._cell_update_due():
                await asyncio.sleep(COMMAND_PAUSE)
                bat = await self.pylontech.bat()
                for index, cell_data in enumerate(bat.values):
                    if cell_data.unit not in self._unit_numbers:
                        continue
                    bmu = self.get_unit_number(cell_data.unit)
                    cell = index % 15
                    result.update(
                        {
                            f"{key}_cell_{bmu}_{cell}": sensor.value
                            for key, sensor in cell_data.get_sensors().items()
                        }
                    )
                self._last_cell_update = dt_util.utcnow()

            self._add_calculated_values(result)
            return result

        except Exception as ex:
            raise UpdateFailed(f"Pylontech update failed: {ex}") from ex
        finally:
            if connected:
                await self._safe_disconnect()

    def _cell_update_due(self) -> bool:
        interval = self.entry.options.get(
            CONF_CELL_SCAN_INTERVAL, DEFAULT_CELL_SCAN_INTERVAL
        )
        if self._last_cell_update is None:
            return True
        return (dt_util.utcnow() - self._last_cell_update).total_seconds() >= interval

    def _add_calculated_values(self, data: dict[str, Any]) -> None:
        """Add useful diagnostics and warning states."""
        voltage = _float(data.get("volt"))
        current = _float(data.get("curr"))
        cell_low = _float(data.get("cell_volt_low"))
        cell_high = _float(data.get("cell_volt_high"))
        temp_low = _float(data.get("cell_temp_low"))
        temp_high = _float(data.get("cell_temp_high"))

        data["diag_power_w"] = (
            voltage * current if voltage is not None and current is not None else None
        )
        data["diag_cell_delta_v"] = (
            cell_high - cell_low
            if cell_high is not None and cell_low is not None
            else None
        )
        data["diag_temp_delta_k"] = (
            temp_high - temp_low
            if temp_high is not None and temp_low is not None
            else None
        )

        delta_limit = (
            self.entry.options.get(
                CONF_WARN_CELL_DELTA_MV, DEFAULT_WARN_CELL_DELTA_MV
            )
            / 1000.0
        )
        max_temp = self.entry.options.get(
            CONF_WARN_MAX_CELL_TEMP, DEFAULT_WARN_MAX_CELL_TEMP
        )
        min_v = self.entry.options.get(
            CONF_WARN_MIN_CELL_VOLTAGE, DEFAULT_WARN_MIN_CELL_VOLTAGE
        )
        max_v = self.entry.options.get(
            CONF_WARN_MAX_CELL_VOLTAGE, DEFAULT_WARN_MAX_CELL_VOLTAGE
        )

        data["warn_cell_imbalance"] = bool(
            data["diag_cell_delta_v"] is not None
            and data["diag_cell_delta_v"] >= delta_limit
        )
        data["warn_temperature"] = bool(
            temp_high is not None and temp_high >= max_temp
        )
        data["warn_cell_voltage"] = bool(
            (cell_low is not None and cell_low <= min_v)
            or (cell_high is not None and cell_high >= max_v)
        )

        error_code = str(data.get("error_code") or "").strip().lower()
        state_problem = any(
            str(data.get(key) or "").strip().lower() not in ("", "normal")
            for key in (
                "volt_state",
                "curr_state",
                "temp_state",
                "cell_volt_state",
                "cell_temp_state",
                "unit_volt_state",
                "unit_temp_state",
            )
        )
        data["warn_bms_state"] = state_problem or error_code not in (
            "",
            "0",
            "0x0",
        )
        # Only actual BMS state/error information is exposed as a BMS warning.
        # Diagnostic thresholds remain separate observations.
        data["warn_any"] = data["warn_bms_state"]

        messages: list[str] = []
        if data["warn_bms_state"]:
            messages.append(f"BMS-Status/Fehlercode: {data.get('error_code')}")
        data["warn_message"] = "; ".join(messages) if messages else "Keine BMS-Warnung"

        # Force-H2 balancing maintenance is a periodic full charge. Remember
        # observed full charges locally and recommend another after 90 days.
        soc = _float(data.get("charge_ah_perc"))
        now = dt_util.utcnow()
        if soc is not None and soc >= 99.0:
            if self._last_full_charge is None or (now - self._last_full_charge) >= timedelta(hours=12):
                self._last_full_charge = now
                self.hass.async_create_task(
                    self._storage.async_save({"last_full_charge": now.isoformat()})
                )

        data["last_full_charge"] = self._last_full_charge
        data["balance_recommended"] = bool(
            self._last_full_charge is not None
            and now - self._last_full_charge >= timedelta(days=90)
        )

    async def _safe_disconnect(self) -> None:
        try:
            await self.pylontech.disconnect()
        except Exception:
            _LOGGER.debug("Error while disconnecting", exc_info=True)

    def sensor_value(self, sensor: str) -> Any:
        return (self.data or {}).get(sensor)

    def get_number_of_units(self) -> int:
        return len(self.unit_device_infos)

    def get_unit_number(self, unit_idx: int) -> int:
        return self._unit_numbers[unit_idx]


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _device(info: InfoCommand) -> DeviceInfo:
    serial = info.module_barcode.value or "Pylontech-HV"
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        name="Pylontech HV BMS",
        model=info.device_name.value or "SC0500",
        manufacturer=info.manufacturer.value or "Pylontech",
        sw_version=f"{info.main_sw_version.value or '-'} / {info.sw_version.value or '-'}",
        hw_version=info.board_version.value,
        serial_number=serial,
    )


def _unit_device(info: InfoCommand, idx: int, serial: str) -> DeviceInfo:
    parent = info.module_barcode.value or "Pylontech-HV"
    return DeviceInfo(
        identifiers={(DOMAIN, serial)},
        name=f"Pylontech BMU #{idx}",
        manufacturer=info.manufacturer.value or "Pylontech",
        via_device=(DOMAIN, parent),
        serial_number=serial,
    )
