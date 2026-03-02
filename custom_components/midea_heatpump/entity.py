"""Base entity for Midea ATW Heat Pump."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, DOMAIN
from .coordinator import MideaHeatPumpCoordinator


class MideaHeatPumpEntity(CoordinatorEntity[MideaHeatPumpCoordinator]):
    """Base class for all Midea ATW Heat Pump entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: MideaHeatPumpCoordinator, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_name = name
        device_id = str(coordinator.entry.data[CONF_DEVICE_ID])
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name="Midea ATW Heat Pump",
            manufacturer="Midea",
            model="FlexFit ATW R32",
        )
