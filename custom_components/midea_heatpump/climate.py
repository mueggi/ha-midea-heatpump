"""Climate platform for Midea ATW Heat Pump (Zone 1 heating control)."""

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

from .const import DOMAIN, MAX_ZONE_TEMP, MIN_ZONE_TEMP
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Zone 1 climate entity."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MideaZone1Climate(coordinator)])


class MideaZone1Climate(MideaHeatPumpEntity, ClimateEntity):
    """Zone 1 heating control with thermostat UI."""

    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_min_temp = MIN_ZONE_TEMP
    _attr_max_temp = MAX_ZONE_TEMP
    _attr_target_temperature_step = 1
    _attr_assumed_state = True

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "zone1_climate", "Zone 1 Heating")
        self._target_temp: float | None = None

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
        """Return last-set zone 1 target (assumed state, not readable)."""
        return self._target_temp

    async def async_set_temperature(self, **kwargs) -> None:
        """Set the zone 1 target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is not None:
            await self.hass.async_add_executor_job(
                self.coordinator.device.set_attribute, "zone1_target_temp", temp
            )
            self._target_temp = float(temp)
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """HVAC mode is fixed to HEAT (no power toggle available)."""
