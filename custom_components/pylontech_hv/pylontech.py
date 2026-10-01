"""Package for reading data from Pylontech (high voltage) BMS.

The 'info' BMS command returns list of BMU from top to bottom.
Topmost unit, first in chain, right after BMS iself is reported as BMU #0.
The last in chain is BBU #n-1

However the 'unit' and 'bat' BMS commands seem to report units/cells
in reversed order !
Unit with index 1 is the last one in chain - BMU #n-1
Cells with index 0-14 are from the last unit in chain.
"""

from __future__ import annotations

import asyncio
from asyncio import StreamReader, StreamWriter
from dataclasses import dataclass
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


@dataclass
class Sensor:
    """Definition of inverter sensor and its attributes."""

    name: str
    unit: str
    value: Any

    def __str__(self):
        """Return string representation of sensor."""
        return f"{self.name}: {self.value} {self.unit}"

    def set(self, source: str) -> Sensor:
        """Decode and set value from source string."""
        return self

    def setValue(self, source: str) -> Sensor:
        """Decode and set value from source line.

        The input line is assumed to be of a "Label : value" form,
        so the value starts after first ":" character.
        """
        self.set(source[source.index(":") + 1 :])
        return self


class HasSensors:
    """Supeclass for BMS types with sensors attributres."""

    def get_sensors(self) -> dict[str, Sensor]:
        """Return sensor values provided by the command."""
        return {k: v for k, v in vars(self).items() if isinstance(v, Sensor)}


class Text(Sensor):
    """Sensor representing text value."""

    def __init__(self, name: str) -> None:
        """Initialize the text sensor."""
        super().__init__(name, " ", None)

    def set(self, source: str) -> Text:
        """Decode and set value from source string."""
        self.value = source
        return self

    def fetch(self, source: list[str], lookup: str | None = None) -> Text:
        """Decode (if present) and set value (after : separator) from list of string."""
        if (lookup if lookup else self.name) in source[0]:
            self.value = source[0].split(":")[1]
            source.pop(0)
        return self


class Boolean(Sensor):
    """Sensor representing Y/N value."""

    def __init__(self, name: str) -> None:
        """Initialize the text sensor."""
        super().__init__(name, "Y/N", None)

    def set(self, source: str) -> Text:
        """Decode and set value from source string."""
        self.value = source in {"Y", "y"}
        return self


class Integer(Sensor):
    """Sensor representing integer value."""

    def __init__(self, name: str) -> None:
        """Initialize the integer sensor."""
        super().__init__(name, "", None)

    def set(self, source: str) -> Integer:
        """Decode and set value from source string."""
        self.value = int(source)
        return self

    def fetch(self, source: list[str], lookup: str | None = None) -> Integer:
        """Decode (if present) and set value (after : separator) from list of string."""
        if (lookup if lookup else self.name) in source[0]:
            self.value = int(source[0].split(":")[1])
            source.pop(0)
        return self


class Percent(Sensor):
    """Sensor representing percent value."""

    def __init__(self, name: str) -> None:
        """Initialize the percent sensor."""
        super().__init__(name, "%", None)

    def set(self, source: str) -> Percent:
        """Decode and set value from source string."""
        self.value = int(source.replace("%", ""))
        return self


class Current(Sensor):
    """Sensor representing current [A]."""

    def __init__(self, name: str) -> None:
        """Initialize the current sensor."""
        super().__init__(name, "A", None)

    def set(self, source: str, divider: int = 1000) -> Current:
        """Decode and set value from source string."""
        try:
            self.value = int(source) / divider
        except ValueError:
            self.value = int(source.replace("mA", "")) / divider
        return self

    def fetch(self, source: list[str], lookup: str | None = None) -> Current:
        """Decode (if present) and set value (after : separator) from list of string."""
        if (lookup if lookup else self.name) in source[0]:
            self.value = int(source[0].split(":")[1].replace("mA", ""))
            source.pop(0)
        return self


class Voltage(Sensor):
    """Sensor representing voltage [V]."""

    def __init__(self, name: str) -> None:
        """Initialize the voltage sensor."""
        super().__init__(name, "V", None)

    def set(self, source: str, divider: int = 1000) -> Voltage:
        """Decode and set value from source string."""
        self.value = int(source) / divider
        return self

    def setValue(self, source: str, divider: int = 1000) -> Sensor:
        """Decode and set value from source line.

        The input line is assumed to be of a "Label : value" form,
        so the value starts after first ":" character.
        """
        self.set(source[source.index(":") + 1 :], divider)
        return self


class ChargeAh(Sensor):
    """Sensor representing charge [Ah]."""

    def __init__(self, name: str) -> None:
        """Initialize the charge sensor."""
        super().__init__(name, "Ah", None)

    def set(self, source: str, divider: int = 1000) -> ChargeAh:
        """Decode and set value from source string."""
        self.value = int(source) / divider
        return self


class ChargeWh(Sensor):
    """Sensor representing charge [Wh]."""

    def __init__(self, name: str) -> None:
        """Initialize the charge sensor."""
        super().__init__(name, "Wh", None)

    def set(self, source: str, divider: int = 1) -> ChargeWh:
        """Decode and set value from source string."""
        self.value = int(source) / divider
        return self


class Temp(Sensor):
    """Sensor representing temperature [C]."""

    def __init__(self, name: str) -> None:
        """Initialize the temp sensor."""
        super().__init__(name, "C", None)

    def set(self, source: str) -> Temp:
        """Decode and set value from source string."""
        self.value = int(source) / 1000
        return self


class UnitCommand:
    """Pylontech BMS console command 'unit'."""

    def __init__(self, lines: list[str]) -> None:
        """Initialize the unit command."""
        self.values: list[UnitValues] = []

        # SC0500:
        #   Time:...
        #   Index Volt Curr Tmpr AvgTempr ...
        #   0 ...
        #
        # Keep only the table header and actual unit rows.
        header = next((line for line in lines if line.lstrip().startswith("Index")), "")
        data_lines = [
            line for line in lines
            if line.split() and line.split()[0].isdigit()
        ]

        nr_of_units = len(data_lines)

        for line in data_lines:
            # Pylontech reports units in reverse physical order.
            self.values.insert(0, UnitValues(line, header, nr_of_units))

    def __str__(self) -> str:
        """Return string representation of unit command."""
        result = ""
        for val in self.values:
            result += str(val)
            result += "\n"
        return result


class UnitValues(HasSensors):
    """Class representing parameters of a unit (battery module)."""

    def __init__(self, line: str, header: str, nr_of_units: int) -> None:
        """Initialize the unit values object."""
        chunks = line.split()

        raw_position = int(chunks.pop(0))
        self.position = Integer("Position").set(str(nr_of_units - 1 - raw_position))

        # SC0500 / XHB_CMU_H7 format
        if "AvgTempr" in header:
            self.volt = Voltage("Voltage").set(chunks.pop(0))
            self.curr = Current("Current").set(chunks.pop(0))
            self.temp = Temp("Temperature").set(chunks.pop(0))

            self.avg_temp = Temp("Average temperature").set(chunks.pop(0))
            self.bpt_temp = Temp("BPT temperature").set(chunks.pop(0))
            self.bnt_temp = Temp("BNT temperature").set(chunks.pop(0))

            self.cell_temp_low = Temp("Lowest cell temperature").set(chunks.pop(0))
            self.cell_temp_high = Temp("Highest cell temperature").set(chunks.pop(0))
            self.cell_volt_low = Voltage("Lowest cell voltage").set(chunks.pop(0))
            self.cell_volt_high = Voltage("Highest cell voltage").set(chunks.pop(0))

            # Fan values are "Null" on units without fans, so expose them as text.
            self.fan_pwm = Text("Fan PWM").set(chunks.pop(0))
            self.fan1_rpm = Text("Fan 1 RPM").set(chunks.pop(0))
            self.fan2_rpm = Text("Fan 2 RPM").set(chunks.pop(0))

            self.base_state = Text("Basic state").set(chunks.pop(0))
            self.volt_state = Text("Voltage state").set(chunks.pop(0))
            self.temp_state = Text("Temperature state").set(chunks.pop(0))
            self.bpt_temp_state = Text("BPT temperature state").set(chunks.pop(0))
            self.bnt_temp_state = Text("BNT temperature state").set(chunks.pop(0))
            self.fan1_state = Text("Fan 1 state").set(chunks.pop(0))
            self.fan2_state = Text("Fan 2 state").set(chunks.pop(0))

            self.charge_ah_perc = Percent("Charge Ah %").set(chunks.pop(0))
            self.charge_ah = ChargeAh("Charge Ah").set(chunks.pop(0))
            if chunks and chunks[0].lower() == "mah":
                chunks.pop(0)

            if chunks:
                self.charge_wh_perc = Percent("Charge Wh %").set(chunks.pop(0))
            if chunks:
                # SC0500 reports this field in mWh.
                self.charge_wh_wh = ChargeWh("Charge Wh").set(chunks.pop(0), 1000)
            if chunks and chunks[0].lower() in {"wh", "mwh"}:
                chunks.pop(0)

        # Older format supported by the original integration
        else:
            self.volt = Voltage("Voltage").set(chunks.pop(0))
            self.curr = Current("Current").set(chunks.pop(0))
            self.temp = Temp("Temperature").set(chunks.pop(0))
            self.cell_temp_low = Temp("Lowest cell temperature").set(chunks.pop(0))
            self.cell_temp_high = Temp("Highest cell temperature").set(chunks.pop(0))
            self.cell_volt_low = Voltage("Lowest cell voltage").set(chunks.pop(0))
            self.cell_volt_high = Voltage("Highest cell voltage").set(chunks.pop(0))
            self.base_state = Text("Basic state").set(chunks.pop(0))
            self.volt_state = Text("Voltage state").set(chunks.pop(0))
            self.temp_state = Text("Temperature state").set(chunks.pop(0))
            self.charge_ah_perc = Percent("Charge Ah %").set(chunks.pop(0))
            self.charge_ah = ChargeAh("Charge Ah").set(chunks.pop(0))
            if chunks:
                chunks.pop(0)  # mAH
            if "CoulombWH" in header and chunks:
                self.charge_wh_perc = Percent("Charge Wh %").set(chunks.pop(0))
                if chunks:
                    self.charge_wh_wh = ChargeWh("Charge Wh").set(chunks.pop(0))

    def __str__(self):
        """Return string representation of unit values."""
        result = ""
        for each in vars(self).values():
            result += str(each)
            result += "\n"
        return result


class PwrCommand(HasSensors):
    """Pylontech BMS console command 'pwr'."""

    def __init__(self, lines: list[str]) -> None:
        """Initialize the pwr command."""

        # Different Pylontech HV firmware versions add different preamble
        # fields. SC0500 / XHB_CMU_H7 uses:
        # Time, Bat.Avg.Tmpr, D+D-.Volt and B+B-.Volt.
        while lines and not lines[0].lstrip().startswith("Volt"):
            line = lines[0]

            if line.startswith("Time:"):
                lines.pop(0)
                continue

            if "Bat.Avg.Tmpr" in line or "Average" in line:
                self.avg_temp = Temp("Average temperature").setValue(lines.pop(0))
                continue

            if "D+D-.Volt" in line or "DC" in line:
                self.dc_voltage = Voltage("DC Voltage").setValue(lines.pop(0))
                continue

            if "B+B-.Volt" in line or "Bat Voltage" in line:
                self.bat_voltage = Voltage("Bat Voltage").setValue(lines.pop(0))
                continue

            # Unknown preamble line: ignore it rather than trying to parse
            # text as a number.
            lines.pop(0)

        if len(lines) < 2:
            raise ValueError("pwr response does not contain expected table")

        header = lines.pop(0)
        chunks = lines[0].split()

        self.volt = Voltage("Voltage").set(chunks.pop(0))
        self.curr = Current("Current").set(chunks.pop(0))
        self.temp = Temp("Temperature").set(chunks.pop(0))
        self.cell_temp_low = Temp("Lowest cell temperature").set(chunks.pop(0))
        self.cell_temp_high = Temp("Highest cell temperature").set(chunks.pop(0))
        self.cell_volt_low = Voltage("Lowest cell voltage").set(chunks.pop(0))
        self.cell_volt_high = Voltage("Highest cell voltage").set(chunks.pop(0))
        self.unit_temp_low = Temp("Lowest unit temperature").set(chunks.pop(0))
        self.unit_temp_high = Temp("Highest unit temperature").set(chunks.pop(0))
        self.unit_volt_low = Voltage("Lowest unit voltage").set(chunks.pop(0))
        self.unit_volt_high = Voltage("Highest unit voltage").set(chunks.pop(0))
        self.base_state = Text("Basic state").set(chunks.pop(0))
        self.volt_state = Text("Voltage state").set(chunks.pop(0))
        self.curr_state = Text("Current state").set(chunks.pop(0))
        self.temp_state = Text("Temperature state").set(chunks.pop(0))
        self.charge_ah_perc = Percent("Charge Ah %").set(chunks.pop(0))
        self.charge_ah = ChargeAh("Charge Ah").set(chunks.pop(0))

        if chunks and chunks[0].lower() == "mah":
            chunks.pop(0)

        if "CoulombWH" in header:
            self.charge_wh_perc = Percent("Charge Wh %").set(chunks.pop(0))
            # SC0500 reports mWh here.
            self.charge_wh_wh = ChargeWh("Charge Wh").set(chunks.pop(0), 1000)
            if chunks and chunks[0].lower() in {"wh", "mwh"}:
                chunks.pop(0)

        # Older firmware may append date + time to this row.
        if (
            len(chunks) >= 7
            and any(sep in chunks[0] for sep in ("-", "/"))
            and ":" in chunks[1]
        ):
            chunks.pop(0)
            chunks.pop(0)

        if len(chunks) < 5:
            raise ValueError(f"pwr response has too few status fields: {chunks!r}")

        self.cell_volt_state = Text("Cell voltage state").set(chunks.pop(0))
        self.cell_temp_state = Text("Cell temperature state").set(chunks.pop(0))
        self.unit_volt_state = Text("Unit voltage state").set(chunks.pop(0))
        self.unit_temp_state = Text("Unit temperature state").set(chunks.pop(0))
        self.error_code = Text("Error code").set(chunks.pop(0))

    def __str__(self):
        """Return string representation of pwr command."""
        result = ""
        for each in vars(self).values():
            result += str(each)
            result += "\n"
        return result


class BatCommand(HasSensors):
    """Pylontech BMS console command 'bat'."""

    def __init__(self, lines: list[str]) -> None:
        """Initialize the bat sensor."""

        if lines and lines[0].startswith("Time:"):
            lines.pop(0)

        if lines and ("A.Tempr" in lines[0] or "Tempr" in lines[0]):
            self.avg_temp = Temp("Average Temperature").setValue(lines.pop(0))

        if lines and ("C.Curr" in lines[0] or "Charge" in lines[0]):
            self.charge_curr = Current("Charge Current").setValue(lines.pop(0))

        if lines and ("D.Curr" in lines[0] or "Discharge" in lines[0]):
            self.discharge_curr = Current("Discharge Current").setValue(lines.pop(0))

        if lines and ("B.State" in lines[0] or "State" in lines[0]):
            self.b_state = Text("Bat State").setValue(lines.pop(0))

        # Some firmware versions include an extra "label : voltage" line
        # before the table. Do not mistake the table header ("Bat Volt Curr...")
        # for that field.
        if lines and ":" in lines[0] and "Volt" in lines[0]:
            self.bal_volt = Voltage("Bat Voltage").setValue(lines.pop(0), 10)

        if not lines:
            raise ValueError("bat response does not contain a cell table")

        header = lines.pop(0)

        self.values: list[BatValues] = []
        data_lines = [
            line for line in lines
            if line.split() and line.split()[0].isdigit()
        ]

        # bat reports the cells in reverse unit order. There are 15 cells
        # per H48050 module on this SC0500 stack.
        cell = len(data_lines) - 1
        for line in data_lines:
            self.values.append(BatValues(line, header, int(cell / 15)))
            cell -= 1

    def __str__(self) -> str:
        """Return string representation of bat command."""
        result = ""
        for val in vars(self).values():
            if val is not None:
                result += str(val)
                result += "\n"
        return result


class BatValues(HasSensors):
    """Class representing parameters of a battery cell."""

    def __init__(self, line: str, header: str, unit: int) -> None:
        """Initialize the bat values object."""
        chunks = line.split()
        self.unit = unit

        chunks.pop(0)  # Cell index
        self.volt = Voltage("Cell voltage").set(chunks.pop(0))
        self.curr = Current("Cell current").set(chunks.pop(0))
        self.tempr = Temp("Cell temperature").set(chunks.pop(0))
        self.v_state = Text("Cell voltage state").set(chunks.pop(0))
        self.t_state = Text("Cell temperature state").set(chunks.pop(0))

        # SC0500 data rows contain:
        # AH% AH(mAh) WH% WH(mWh) Bal
        self.charge_ah_perc = Percent("Cell charge Ah %").set(chunks.pop(0))
        self.charge_ah = ChargeAh("Cell charge Ah").set(chunks.pop(0))

        if "WH" in header and len(chunks) >= 3:
            self.charge_wh_perc = Percent("Cell charge Wh %").set(chunks.pop(0))
            self.charge_wh = ChargeWh("Cell charge Wh").set(chunks.pop(0), 1000)

        self.bal = Text("Cell balance").set(chunks.pop(0))

    def __str__(self):
        """Return string representation of cell values."""
        result = ""
        for each in vars(self).values():
            result += str(each)
            result += "\n"
        return result


class InfoCommand(HasSensors):
    """Pylontech BMS console command 'info'."""

    def __init__(self, lines: list[str]) -> None:
        """Initialize the info command."""

        # Parse by exact label instead of relying on a fixed order. This is
        # required for SC0500 firmware which omits some fields and adds others.
        fields: dict[str, str] = {}
        for line in lines:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()

        def text_sensor(name: str, *keys: str) -> Text:
            sensor = Text(name)
            for key in keys:
                if key in fields:
                    sensor.set(fields[key])
                    break
            return sensor

        def int_sensor(name: str, *keys: str) -> Integer:
            sensor = Integer(name)
            for key in keys:
                if key in fields:
                    sensor.set(fields[key])
                    break
            return sensor

        def current_sensor(name: str, *keys: str) -> Current:
            sensor = Current(name)
            for key in keys:
                if key in fields:
                    sensor.set(fields[key])
                    break
            return sensor

        self.device_address = int_sensor("Device address", "Device address")
        self.manufacturer = text_sensor("Manufacturer", "Manufacturer")
        self.device_name = text_sensor("Device name", "Device name")
        self.board_version = text_sensor("Board version", "Board version")
        self.hard_version = text_sensor("Hard version", "Hard version")
        self.main_sw_version = text_sensor("Main Soft version", "Main Soft version")
        self.sw_version = text_sensor("Soft version", "Soft  version", "Soft version")
        self.boot_version = text_sensor("Boot version", "Boot  version", "Boot version")
        self.comm_version = text_sensor("Comm version", "Comm version")
        self.release_date = text_sensor("Release Date", "Release Date")

        self.barcode = text_sensor("Barcode", "Barcode")
        self.pcba_barcode = text_sensor("PCBA Barcode", "PCBA Barcode")
        self.module_barcode = text_sensor("Module Barcode", "Module Barcode")
        self.pwr_supply_barcode = text_sensor(
            "PowerSupply Barcode", "PowerSupply Barcode"
        )
        self.device_test_time = text_sensor("Device Test Time", "Device Test Time")
        self.specification = text_sensor("Specification", "Specification")
        self.cell_number = int_sensor("Cell Number", "Cell Number")

        self.max_discharge_current = current_sensor(
            "Max Discharge Curr", "Max Dischg Curr", "Max Discharge Curr"
        )
        self.max_charge_current = current_sensor(
            "Max Charge Curr", "Max Charge Curr"
        )

        self.shut_circuit = text_sensor("Shut Circuit", "Shut Circuit")
        self.relay_feedback = text_sensor("Relay Feedback", "Relay Feedback")
        self.new_board = text_sensor("New Board", "New Board")

        self.bmu_modules: list[str] = []
        self.bmu_pcbas: list[str] = []

        # Keep compatibility with firmware versions that report individual
        # BMU serial numbers.
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Module") and not stripped.startswith("Module Barcode"):
                parts = stripped.split()
                if len(parts) >= 3:
                    self.bmu_modules.insert(0, parts[2])

            if stripped.startswith("PCBA") and not stripped.startswith("PCBA Barcode"):
                parts = stripped.split()
                if len(parts) >= 3:
                    self.bmu_pcbas.insert(0, parts[2])

        # SC0500 / XHB_CMU_H7 does not expose individual BMU serial numbers
        # in "info". Derive the number of modules from the cell count and
        # create stable virtual IDs. H48050 modules contain 15 cells each.
        if not self.bmu_modules and self.cell_number.value:
            module_count = int(self.cell_number.value / 15)
            base_id = self.module_barcode.value or "SC0500"
            self.bmu_modules = [
                f"{base_id}-BMU-{idx:02d}" for idx in range(module_count)
            ]

    def __str__(self) -> str:
        """Return string representation of info command."""
        result = ""
        for val in vars(self).values():
            if val is not None:
                result += str(val)
                result += "\n"
        return result


class PylontechBMS:
    """Pylontech BMS connection class."""

    _END_PROMPTS = ("Command completed successfully", "$$")

    def __init__(self, host: str, port: int) -> None:
        """Initialize the BMS object."""
        self.host: str = host
        self.port: int = port
        self.reader: StreamReader | None = None
        self.writer: StreamWriter | None = None
        self.bmus: tuple[str] = ()

    async def _exec_cmd(self, cmd: str) -> list[str]:
        """Send a command to the BMS and parse the response."""
        if self.writer is None or self.reader is None:
            raise ConnectionError("Pylontech BMS is not connected")

        # The SC0500 returns a large response for the 'bat' command
        # (150 cells), so give it more time and use a larger read buffer.
        read_timeout = 12 if cmd == "bat" else 7

        self.writer.write((cmd + "\n").encode("ascii"))
        await asyncio.wait_for(self.writer.drain(), 5)

        lines: list[str] = []
        linebytes = bytearray()

        while True:
            try:
                data = await asyncio.wait_for(
                    self.reader.read(512),
                    read_timeout,
                )
            except TimeoutError as err:
                raise TimeoutError(
                    f"Timeout while waiting for Pylontech '{cmd}' response"
                ) from err

            if not data:
                raise ConnectionError(
                    f"Pylontech connection closed while reading '{cmd}'"
                )

            prompt_seen = False

            for i in data:
                # Pylontech mixes LF and CR+LF line endings.
                if i not in (13, 10):
                    linebytes.append(i)

                    # The Pylontech prompt normally has NO trailing CR/LF.
                    # Detect it immediately instead of waiting for another
                    # byte/read that will never arrive.
                    if linebytes in (b"pylon>", b"pylon_debug>"):
                        prompt_seen = True
                        linebytes = bytearray()
                        break

                    continue

                if not linebytes:
                    continue

                line = linebytes.decode("ascii", errors="replace")
                linebytes = bytearray()

                if line in ("pylon>", "pylon_debug>"):
                    prompt_seen = True
                    break

                if line not in self._END_PROMPTS:
                    lines.append(line)

            if prompt_seen:
                break

        if not lines:
            raise ValueError(f"Empty response to Pylontech command '{cmd}'")

        if lines.pop(0) != cmd:
            raise ValueError(
                f"Unexpected response to command '{cmd}'"
            )

        if not lines or lines.pop(0) != "@":
            raise ValueError(
                f"Missing '@' marker in response to '{cmd}'"
            )

        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "Response to Pylontech command '%s':",
                cmd,
            )
            for line in lines:
                _LOGGER.debug(line)

        return lines

    async def connect(self) -> None:
        """Connect to BMS console."""
        self.reader, self.writer = await asyncio.wait_for(
            asyncio.open_connection(self.host, self.port),
            5,
        )

        # Give the ESP stream server / Pylontech console a moment after a
        # fresh TCP connection before sending the next console command.
        await asyncio.sleep(0.5)

    async def disconnect(self) -> None:
        """Diconnect from BMS console."""
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
            self.reader = None
            self.writer = None

    async def bat(self) -> BatCommand:
        """Invoke the 'bat' console command."""
        return BatCommand(await self._exec_cmd("bat"))

    async def info(self) -> InfoCommand:
        """Invoke the 'info' console command."""
        result = InfoCommand(await self._exec_cmd("info"))
        self.bmus = tuple(result.bmu_modules)
        return result

    async def pwr(self) -> PwrCommand:
        """Invoke the 'pwr' console command."""
        return PwrCommand(await self._exec_cmd("pwr"))

    async def unit(self) -> UnitCommand:
        """Invoke the 'unit' console command."""
        return UnitCommand(await self._exec_cmd("unit"))
