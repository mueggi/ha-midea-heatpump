"""Number platform for Midea ATW Heat Pump (zone target temperatures)."""

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_ZONE_TEMP, MIN_ZONE_TEMP
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up zone target temperature number entities."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MideaZone1TargetNumber(coordinator)])


class MideaZone1TargetNumber(MideaHeatPumpEntity, NumberEntity):
    """Zone 1 heating target temperature (assumed state -- not readable from device)."""

    _attr_assumed_state = True
    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = MIN_ZONE_TEMP
    _attr_native_max_value = MAX_ZONE_TEMP
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "zone1_target_temp", "Zone 1 Target Temperature")
        self._attr_native_value = 35.0  # Default assumed value

    async def async_set_native_value(self, value: float) -> None:
        """Set the zone 1 target temperature (untested -- assumed state)."""
        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute, "zone1_target_temp", value
        )
        self._attr_native_value = value
        self.async_write_ha_state()
