"""Water heater platform for Midea ATW Heat Pump (DHW control)."""

import logging

from homeassistant.components.water_heater import (
    STATE_HEAT_PUMP,
    STATE_OFF,
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_DHW_TEMP, MIN_DHW_TEMP
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the DHW water heater entity."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MideaDHWWaterHeater(coordinator)])


class MideaDHWWaterHeater(MideaHeatPumpEntity, WaterHeaterEntity):
    """DHW (domestic hot water) control via confirmed SET command."""

    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_DHW_TEMP
    _attr_max_temp = MAX_DHW_TEMP
    _attr_target_temperature_step = 1
    _attr_operation_list = [STATE_HEAT_PUMP, STATE_OFF]

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "dhw", "DHW")

    @property
    def current_temperature(self) -> float | None:
        """Return the current DHW tank temperature."""
        if self.coordinator.data:
            return self.coordinator.data.get("t1_dhw_tank")
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target DHW temperature."""
        if self.coordinator.data:
            return self.coordinator.data.get("dhw_target_temp")
        return None

    @property
    def current_operation(self) -> str:
        """Return current operation based on power state."""
        if self.coordinator.data and self.coordinator.data.get("power"):
            return STATE_HEAT_PUMP
        return STATE_OFF

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the DHW target temperature (confirmed working)."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.hass.async_add_executor_job(
                self.coordinator.device.set_attribute, "dhw_target_temp", temp
            )
            await self.coordinator.async_request_refresh()
