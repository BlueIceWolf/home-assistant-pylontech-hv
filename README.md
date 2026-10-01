# Pylontech HV BMS for Home Assistant

Custom Home Assistant integration for Pylontech high-voltage BMS systems,
initially tested with an **SC0500 / XHB_CMU_H7**, 10 battery modules and
150 cells.

## Features

- Local polling over a TCP-to-UART console bridge
- `info`, `pwr`, `unit` and `bat` parsing
- SC0500-specific console format support
- BMS + individual BMU devices in Home Assistant
- Optional individual cell entities
- Configurable polling intervals
- Cell polling can run slower than normal BMS polling
- Calculated pack power
- Calculated cell-voltage spread
- Calculated cell-temperature spread
- Integrated warning binary sensors
- Configurable warning thresholds
- Downloadable Home Assistant diagnostics
- German and English setup/options text

## Tested setup

- Pylontech SC0500 / XHB_CMU_H7
- Specification reported by BMS: 480 V / 50 Ah
- 150 cells
- 10 modules with 15 cells each
- ESPHome stream server exposing the Pylontech console over TCP

Default TCP port is `1234`.

## Installation with HACS

1. Add this repository to HACS as a **Custom repository**.
2. Type: **Integration**
3. Install **Pylontech HV BMS**.
4. Restart Home Assistant.
5. Go to **Settings → Devices & services → Add integration**.
6. Search for **Pylontech HV BMS**.
7. Enter the TCP bridge host/IP and port.

## Options

After setup, open the integration options.

### Polling

- Main polling interval: 10–300 seconds
- Cell polling interval: 30–3600 seconds

Cell data is intentionally allowed to update more slowly because the `bat`
command is much larger than the normal `pwr` and `unit` responses.

### Cell entities

- `none`: no individual cell entities
- `voltage`: only individual cell voltages
- `full`: all parsed cell values

### Module details

Disabled by default. When enabled, all parsed BMU values are exposed.

## Warning sensors

The integration creates problem binary sensors for:

- Any active warning
- Cell imbalance
- High cell temperature
- Cell voltage outside configured limits
- BMS status / error-code warning

The thresholds can be changed in the integration options.

The main warning entity contains a human-readable message as an attribute.

## Diagnostics

Home Assistant's **Download diagnostics** function is supported.
The host/IP is redacted from the diagnostics output.

## ESP stream server

The tested setup uses `mletenay/esphome-stream-server`.

For large `bat` responses, a larger stream/UART buffer is recommended, for example:

```yaml
stream_server:
  uart_id: uart_bus
  port: 1234
  buffer_size: 4096
```

Also consider increasing the UART RX buffer if supported by your ESPHome setup.

## Compatibility

The first supported target is SC0500 / XHB_CMU_H7. Other Pylontech HV BMS
variants may work, but their console output can differ.

## License

MIT. See `LICENSE` and `NOTICE.md`.
