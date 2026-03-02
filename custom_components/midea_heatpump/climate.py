"""Climate platform for Midea ATW Heat Pump (heating water flow control)."""

import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MAX_HEAT_TEMP, MIN_HEAT_TEMP
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the heating climate entity."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MideaHeatingClimate(coordinator)])


class MideaHeatingClimate(MideaHeatPumpEntity, ClimateEntity):
    """Heating water flow target with thermostat UI."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_min_temp = MIN_HEAT_TEMP
    _attr_max_temp = MAX_HEAT_TEMP
    _attr_target_temperature_step = 1

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "heating", "Heating")

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        return HVACMode.HEAT

    @property
    def current_temperature(self) -> float | None:
        """Return water circuit temperature from C0 response."""
        if self.coordinator.data:
            return self.coordinator.data.get("t2_water_circuit")
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return heating water flow target from C0 response."""
        if self.coordinator.data:
            return self.coordinator.data.get("heat_target_temp")
        return None

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the heating water flow target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.hass.async_add_executor_job(
                self.coordinator.device.set_attribute, "heat_target_temp", temp
            )
            await self.coordinator.async_request_refresh()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """HVAC mode is fixed to HEAT (no power toggle available)."""
