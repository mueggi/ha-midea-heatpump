"""Sensor platform for Midea ATW Heat Pump."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="t1_dhw_tank",
        name="DHW Tank Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="t2_water_circuit",
        name="Water Circuit Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="t3_outdoor",
        name="Outdoor Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up temperature sensor entities."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MideaHeatPumpSensor(coordinator, desc) for desc in SENSOR_DESCRIPTIONS
    )


class MideaHeatPumpSensor(MideaHeatPumpEntity, SensorEntity):
    """Temperature sensor from C0 status response."""

    entity_description: SensorEntityDescription

    def __init__(
        self,
        coordinator: MideaHeatPumpCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key, description.name)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        """Return the sensor value from coordinator data."""
        if self.coordinator.data:
            return self.coordinator.data.get(self._key)
        return None
