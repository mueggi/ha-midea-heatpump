"""Mock homeassistant modules so tests can import the midea sub-packages."""

import sys
from unittest.mock import MagicMock

# Create mock modules for all homeassistant dependencies
HA_MODULES = [
    "homeassistant",
    "homeassistant.config_entries",
    "homeassistant.const",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.update_coordinator",
    "homeassistant.helpers.device_registry",
    "homeassistant.helpers.entity_platform",
    "homeassistant.components",
    "homeassistant.components.sensor",
    "homeassistant.components.switch",
    "homeassistant.components.water_heater",
    "homeassistant.components.climate",
]

for mod in HA_MODULES:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()

# Set commonly used constants
sys.modules["homeassistant.const"].CONF_HOST = "host"
sys.modules["homeassistant.const"].CONF_PORT = "port"
sys.modules["homeassistant.const"].ATTR_TEMPERATURE = "temperature"
sys.modules["homeassistant.const"].UnitOfTemperature = MagicMock()
