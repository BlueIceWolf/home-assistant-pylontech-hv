"""Constants for the Pylontech HV BMS integration."""

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "pylontech_hv"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

DEFAULT_NAME = "Pylontech HV BMS"
DEFAULT_PORT = 1234

CONF_SCAN_INTERVAL = "scan_interval"
CONF_CELL_SCAN_INTERVAL = "cell_scan_interval"
CONF_CELL_ENTITIES = "cell_entities"
CONF_MODULE_DETAILS = "module_details"
CONF_EXTERNAL_POWER_ENTITY = "external_power_entity"
CONF_EXTERNAL_POWER_INVERT = "external_power_invert"

CONF_WARN_CELL_DELTA_MV = "warn_cell_delta_mv"
CONF_WARN_MAX_CELL_TEMP = "warn_max_cell_temp"
CONF_WARN_MIN_CELL_VOLTAGE = "warn_min_cell_voltage"
CONF_WARN_MAX_CELL_VOLTAGE = "warn_max_cell_voltage"

CELL_ENTITIES_NONE = "none"
CELL_ENTITIES_VOLTAGE = "voltage"
CELL_ENTITIES_FULL = "full"

DEFAULT_SCAN_INTERVAL = 30
DEFAULT_CELL_SCAN_INTERVAL = 300
DEFAULT_CELL_ENTITIES = CELL_ENTITIES_VOLTAGE
DEFAULT_MODULE_DETAILS = False
DEFAULT_EXTERNAL_POWER_INVERT = False

DEFAULT_WARN_CELL_DELTA_MV = 30
DEFAULT_WARN_MAX_CELL_TEMP = 50.0
DEFAULT_WARN_MIN_CELL_VOLTAGE = 3.00
DEFAULT_WARN_MAX_CELL_VOLTAGE = 3.60

KEY_COORDINATOR = "coordinator"

# Used only as fallback before the config entry options are available.
SCAN_INTERVAL = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
