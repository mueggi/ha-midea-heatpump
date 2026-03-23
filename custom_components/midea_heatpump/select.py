"""Select platform for Midea ATW Heat Pump (operating mode selection)."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

_LOGGER = logging.getLogger(__name__)

# Operating modes
MODE_DHW = "dhw"
MODE_HEAT = "heat"
MODE_HEAT_DHW = "heat_dhw"

MODE_OPTIONS = [MODE_DHW, MODE_HEAT, MODE_HEAT_DHW]
MODE_NAMES = {
    MODE_DHW: "DHW Only",
    MODE_HEAT: "Heat Only",
    MODE_HEAT_DHW: "Heat + DHW",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select entities."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MideaOperatingModeSelect(coordinator)])


class MideaOperatingModeSelect(MideaHeatPumpEntity, SelectEntity):
    """Select entity for operating mode (DHW/Heat/Heat+DHW)."""

    _attr_options = MODE_OPTIONS

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "operating_mode", "Operating Mode")
        self._attr_current_option = MODE_HEAT_DHW

    @property
    def current_option(self) -> str | None:
        """Return current operating mode from C0 response."""
        if not self.coordinator.data:
            return None

        # Mode is now parsed directly from C0 response byte[2]
        mode = self.coordinator.data.get("mode", "unknown")
        if mode in MODE_OPTIONS:
            return mode
        
        # Fallback to default
        return MODE_HEAT_DHW

    async def async_select_option(self, option: str) -> None:
        """Set the operating mode."""
        if option not in MODE_OPTIONS:
            return

        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute,
            "power_mode",
            {
                "power": True,
                "mode": option,
            },
        )
        self._attr_current_option = option
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def icon(self) -> str:
        """Return icon based on mode."""
        option = self.current_option
        if option == MODE_DHW:
            return "mdi:water-boiler"
        elif option == MODE_HEAT:
            return "mdi:radiator"
        elif option == MODE_HEAT_DHW:
            return "mdi:heat-pump"
        return "mdi:help-circle"
