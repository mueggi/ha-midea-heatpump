"""Switch platform for Midea ATW Heat Pump (ECO, Silent, Disinfect)."""

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
        MideaSilentSwitch(coordinator),
        MideaDisinfectSwitch(coordinator),
    ])


class MideaEcoSwitch(MideaHeatPumpEntity, SwitchEntity):
    """ECO mode switch (assumed state -- device accepts command but can't read back)."""

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


class MideaSilentSwitch(MideaHeatPumpEntity, SwitchEntity):
    """Silent mode switch (assumed state -- device accepts command but can't read back)."""

    _attr_assumed_state = True

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "silent_mode", "Silent Mode")
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on silent mode."""
        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute, "silent_mode", True
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off silent mode."""
        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute, "silent_mode", False
        )
        self._attr_is_on = False
        self.async_write_ha_state()


class MideaDisinfectSwitch(MideaHeatPumpEntity, SwitchEntity):
    """Disinfect mode switch (assumed state -- device accepts command but can't read back)."""

    _attr_assumed_state = True

    def __init__(self, coordinator: MideaHeatPumpCoordinator) -> None:
        super().__init__(coordinator, "disinfect", "Disinfect")
        self._attr_is_on = False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on disinfect mode."""
        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute, "disinfect", True
        )
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off disinfect mode."""
        await self.hass.async_add_executor_job(
            self.coordinator.device.set_attribute, "disinfect", False
        )
        self._attr_is_on = False
        self.async_write_ha_state()
