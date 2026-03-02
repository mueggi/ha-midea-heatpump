"""Number platform for Midea ATW Heat Pump (zone target temperatures)."""

import logging

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_HEAT_TEMP, MAX_ZONE_TEMP, MIN_HEAT_TEMP, MIN_ZONE_TEMP
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up number entities."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        MideaHeatTargetNumber(coordinator),
        MideaZone1TargetNumber(coordinator),
    ])


class MideaHeatTargetNumber(MideaHeatPumpEntity, NumberEntity):
    """Heating water flow target temperature."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = MIN_HEAT_TEMP
    _attr_native_max_value = MAX_HEAT_TEMP
    _attr_native_step = 0.5
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "heat_target_temp", "Heating Target Temperature")

    @property
    def native_value(self) -> float | None:
        """Return heating water flow target from device data."""
        if self.coordinator.data:
            return self.coordinator.data.get("heat_target_temp")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the heating water flow target temperature."""
        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute, "heat_target_temp", value
        )
        await self.coordinator.async_request_refresh()


class MideaZone1TargetNumber(MideaHeatPumpEntity, NumberEntity):
    """Zone 1 heating target temperature."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_min_value = MIN_ZONE_TEMP
    _attr_native_max_value = MAX_ZONE_TEMP
    _attr_native_step = 1.0
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "zone1_target_temp", "Zone 1 Target Temperature")

    @property
    def native_value(self) -> float | None:
        """Return zone 1 target temperature from device data."""
        if self.coordinator.data:
            return self.coordinator.data.get("zone1_target_temp")
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the zone 1 target temperature."""
        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute, "zone1_target_temp", value
        )
        await self.coordinator.async_request_refresh()
