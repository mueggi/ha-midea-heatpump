"""Constants for the Midea ATW Heat Pump integration."""

DOMAIN = "midea_heatpump"

CONF_TOKEN = "token"
CONF_KEY = "key"
CONF_DEVICE_ID = "device_id"
CONF_EMAIL = "email"
CONF_PASSWORD = "password"
CONF_SERVER = "server"

SERVER_SMARTHOME = "SmartHome"
SERVER_NETHOME = "NetHome Plus"
CLOUD_SERVERS = [SERVER_SMARTHOME, SERVER_NETHOME]

DEFAULT_PORT = 6444
POLL_INTERVAL = 30

MIN_DHW_TEMP = 30
MAX_DHW_TEMP = 65
MIN_ZONE_TEMP = 20
MAX_ZONE_TEMP = 55
