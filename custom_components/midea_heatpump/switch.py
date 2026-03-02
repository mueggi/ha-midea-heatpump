"""Switch platform for Midea ATW Heat Pump (ECO, Turbo)."""

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import MideaHeatPumpCoordinator
from .entity import MideaHeatPumpEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch entities."""
    coordinator: MideaHeatPumpCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        MideaEcoSwitch(coordinator),
        MideaTurboSwitch(coordinator),
    ])


class MideaEcoSwitch(MideaHeatPumpEntity, SwitchEntity):
    """ECO mode switch (assumed state -- build_set_eco exists but response unverified)."""

    _attr_assumed_state = True

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "eco_mode", "ECO Mode")
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on ECO mode."""
        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute, "eco_mode", True
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off ECO mode."""
        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute, "eco_mode", False
        )
        self._attr_is_on = False
        self.async_write_ha_state()


class MideaTurboSwitch(MideaHeatPumpEntity, SwitchEntity):
    """Turbo DHW switch (assumed state -- SET command undecoded).

    Needs more Frida captures to implement the actual SET command.
    Currently only updates the assumed state in HA.
    """

    _attr_assumed_state = True

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "fast_dhw", "Turbo DHW")
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on Turbo DHW (stub -- only updates assumed state)."""
        _LOGGER.warning(
            "Turbo DHW control not yet implemented. Setting assumed state only."
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off Turbo DHW (stub -- only updates assumed state)."""
        _LOGGER.warning(
            "Turbo DHW control not yet implemented. Setting assumed state only."
        )
        self._attr_is_on = False
        self.async_write_ha_state()
