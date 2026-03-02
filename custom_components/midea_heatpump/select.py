"""Select platform for Midea ATW Heat Pump (operating mode)."""

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MODE_HEAT_DHW, MODES
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up operating mode select entity."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MideaHeatPumpModeSelect(coordinator)])


class MideaHeatPumpModeSelect(MideaHeatPumpEntity, SelectEntity):
    """Operating mode selector (assumed state -- SET command undecoded).

    Needs more Frida captures to implement the actual SET command for mode changes.
    Currently only updates the assumed state in HA.
    """

    _attr_assumed_state = True
    _attr_options = MODES

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "mode", "Operating Mode")
        self._attr_current_option = MODE_HEAT_DHW  # Default assumed value

    async def async_select_option(self, option: str) -> None:
        """Set operating mode (stub -- only updates assumed state)."""
        _LOGGER.warning(
            "Mode change not yet implemented (needs Frida capture). "
            "Setting assumed state to: %s",
            option,
        )
        self._attr_current_option = option
        self.async_write_ha_state()
