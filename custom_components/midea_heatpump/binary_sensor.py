"""Binary sensor platform for Midea ATW Heat Pump."""

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

BINARY_SENSOR_DESCRIPTIONS = [
    BinarySensorEntityDescription(
        key="zone1_power",
        name="Zone 1 Power",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="dhw_power",
        name="DHW Power",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="compressor_running",
        name="Compressor",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
    BinarySensorEntityDescription(
        key="defrosting",
        name="Defrost",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor entities."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MideaHeatPumpBinarySensor(coordinator, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
    )


class MideaHeatPumpBinarySensor(MideaHeatPumpEntity, BinarySensorEntity):
    """Binary sensor from device status response."""

    entity_description: BinarySensorEntityDescription

    def __init__(
        self,
        coordinator: MideaHeatPumpCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        if self.coordinator.data:
            val = self.coordinator.data.get(self._key)
            if val is not None:
                return bool(val)
        return None
