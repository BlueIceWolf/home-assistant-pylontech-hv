<p align="center">
  <img src="custom_components/pylontech_hv/brand/logo.png" alt="Pylontech HV BMS" width="520">
</p>

<h1 align="center">Pylontech HV BMS for Home Assistant</h1>

<p align="center">
  Local monitoring for Pylontech high-voltage battery systems in Home Assistant.
</p>

---

## What this integration does

**Pylontech HV BMS** reads the service console of a Pylontech high-voltage BMS through a TCP-to-serial bridge and brings the important battery values into Home Assistant.

It was developed and tested with a **Pylontech SC0500 / XHB_CMU_H7** system.

### Highlights

- BMS and every battery module appear as separate Home Assistant devices
- Pack voltage, current, temperature and state of charge
- Module voltage, current, temperature and SOC
- Individual cell voltages
- Minimum and maximum cell voltage and temperature
- Calculated pack power
- Calculated cell-voltage spread
- Calculated temperature spread
- Integrated warning sensors
- Configurable warning limits
- Configurable polling intervals
- Optional detailed module and cell sensors
- Home Assistant diagnostics download
- German and English setup texts
- Fully local — no cloud required

---

## Lovelace card

A matching dashboard card is available separately:

**[Pylontech HV Card](https://github.com/BlueIceWolf/pylontech-hv-card)**

The card is designed to work with this integration and provides a cleaner overview of battery state, BMUs, cell voltages, diagnostics and warnings without having to place many individual entities on a dashboard.

Example:

```yaml
type: custom:pylontech-hv-card
entity: sensor.pylontech_bms_battery
```

See the card repository for installation and configuration details.

---

## Tested hardware

The current version has been tested with:

| Component | Tested setup |
| --- | --- |
| BMS | Pylontech SC0500 / XHB_CMU_H7 |
| Battery system | 480 V / 50 Ah |
| Battery modules | 10 |
| Cells | 150 |
| Cells per module | 15 |
| Connection | Pylontech console via TCP/UART bridge |

Other Pylontech HV systems may work as well, but their console output can differ.

---

## Requirements

You need a TCP bridge connected to the Pylontech console.

The tested setup uses:

**mletenay/esphome-stream-server**

Default TCP port used by this integration:

```text
1234
```

Because the `bat` command returns a lot of data, a larger stream buffer is recommended:

```yaml
stream_server:
  uart_id: uart_bus
  port: 1234
  buffer_size: 4096
```

A larger UART RX buffer is also recommended when supported by your ESPHome configuration.

---

## Installation with HACS

### 1. Add the repository

In HACS:

**HACS → Custom repositories**

Add:

```text
https://github.com/BlueIceWolf/home-assistant-pylontech-hv
```

Select:

```text
Integration
```

### 2. Install

Install **Pylontech HV BMS** and restart Home Assistant.

### 3. Add the integration

Go to:

**Settings → Devices & services → Add integration**

Search for:

```text
Pylontech HV BMS
```

Enter the IP address or hostname of your TCP bridge and its port.

Example:

```text
Host: 192.168.1.170
Port: 1234
```

After setup, the main BMS and all detected BMUs are created automatically.

---

## Configuration

Open:

**Settings → Devices & services → Pylontech HV BMS → Configure**

### Polling intervals

You can configure separate intervals for normal BMS data and the much larger cell-data request.

| Setting | Default |
| --- | ---: |
| Main BMS polling | 30 s |
| Cell polling | 300 s |

Keeping cell polling slower reduces load on the ESP/TCP bridge.

### Cell entities

Choose how much cell information you want:

| Mode | Description |
| --- | --- |
| `none` | No individual cell entities |
| `voltage` | Only individual cell voltages |
| `full` | All parsed cell values |

For most installations, **voltage** is the recommended option.

### Module details

Extended module values can be enabled if you need deeper diagnostics.

By default, only the most useful BMU values are shown to keep Home Assistant clean.

---

## Integrated diagnostics and warnings

The integration creates additional calculated diagnostic values such as:

- Pack power
- Cell-voltage difference
- Cell-temperature difference

It also creates Home Assistant **problem binary sensors** for:

- Cell imbalance
- High cell temperature
- Cell voltage outside configured limits
- BMS status or error-code problems
- Any active BMS warning

The warning thresholds can be changed in the integration options.

The main warning entity also includes a readable explanation in its attributes.

---

## Example device structure

```text
Pylontech HV BMS
├── BMU #0
│   ├── State of charge
│   ├── Voltage
│   ├── Current
│   ├── Temperature
│   ├── Lowest cell voltage
│   ├── Highest cell voltage
│   └── Cell 1–15 voltage
├── BMU #1
├── BMU #2
└── ...
```

---

## Diagnostics download

Home Assistant's built-in **Download diagnostics** function is supported.

The integration includes useful BMS data and warning information while redacting the configured host address.

This makes bug reports much easier.

---

## Troubleshooting

### Integration cannot connect

Check that:

- the ESP/TCP bridge is reachable
- the configured TCP port is correct
- no other program is currently using the Pylontech console
- the Pylontech console has been initialized correctly

### `bat` command times out

The `bat` response can contain data for all cells and is much larger than `pwr` or `unit`.

Increase the ESP stream buffer and avoid polling cell data too frequently.

### Some values show `Null` or `0`

Some Pylontech firmware versions expose fields for hardware that is not fitted, for example fan or additional temperature sensors. These values are not necessarily faults.

---

## Supported console commands

The integration currently uses:

```text
info
pwr
unit
bat
```

Support for additional Pylontech HV models can be added if their console output is available for testing.

---

## Credits

This project is based in part on the work from:

- **mletenay/home-assistant-pylontech**
- **mletenay/esphome-stream-server**

The original code is licensed under the MIT License.

SC0500 / XHB_CMU_H7 support, parser changes, configurable entities, diagnostics and warning features were added for this project.

See [NOTICE.md](NOTICE.md) for attribution details.

---

## License

MIT License. See [LICENSE](LICENSE).

---

### Feedback and other Pylontech HV models

If you use another Pylontech HV BMS, feel free to open an issue and include the output of the relevant console commands.

That can help expand compatibility without guessing the protocol.


### Balancing maintenance

The integration keeps diagnostic cell-voltage/temperature observations separate from actual BMS alarm states. A cell-voltage delta alone is therefore **not** reported as a Pylontech BMS warning.

For Force-H2 systems, an observed full charge (SOC >= 99%) is stored locally as the last balancing/full-charge event. After 90 days without another observed full charge, `binary_sensor` **Ausgleichsladung empfohlen** becomes active. This follows Pylontech's maintenance guidance to periodically charge the system fully for balancing. Until the integration has observed its first full charge, no overdue maintenance alarm is asserted.


## Optional external power comparison

Starting with v1.0.3, the integration can compare the BMS DC power with an optional external Home Assistant power sensor, for example a battery-power value reported by an inverter.

Open the integration options and select **External battery power (optional)**. If the external integration uses the opposite sign convention for charging/discharging, enable **Invert external power sign**.

The integration then exposes:

- External battery power
- Power difference
- Estimated power ratio

The ratio is only calculated when both values are at least 300 W and have the same direction. It is intentionally called a **power ratio**, not inverter efficiency, because the two sensors may use different measurement points and update intervals.
