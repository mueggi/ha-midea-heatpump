"""Constants for the Midea ATW Heat Pump integration."""

DOMAIN = "midea_heatpump"

CONF_TOKEN = "token"
CONF_KEY = "key"
CONF_DEVICE_ID = "device_id"

DEFAULT_PORT = 6444
POLL_INTERVAL = 30

MIN_DHW_TEMP = 30
MAX_DHW_TEMP = 65
MIN_ZONE_TEMP = 20
MAX_ZONE_TEMP = 55

MODE_HEAT = "Heat"
MODE_DHW = "DHW"
MODE_HEAT_DHW = "Heat+DHW"
MODES = [MODE_HEAT, MODE_DHW, MODE_HEAT_DHW]
