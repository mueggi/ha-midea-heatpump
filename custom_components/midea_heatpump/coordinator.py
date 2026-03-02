"""DataUpdateCoordinator for Midea ATW Heat Pump."""

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_DEVICE_ID, CONF_KEY, CONF_TOKEN, DOMAIN, POLL_INTERVAL
from .midea.device import MideaATWDevice

_LOGGER = logging.getLogger(__name__)


class MideaHeatPumpCoordinator(DataUpdateCoordinator[dict]):
    """Coordinator that polls the heat pump every 30s via persistent TCP."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=POLL_INTERVAL),
        )
        self.entry = entry
        self.device = MideaATWDevice(
            ip=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            device_id=entry.data[CONF_DEVICE_ID],
            token=entry.data[CONF_TOKEN],
            key=entry.data[CONF_KEY],
        )

    async def _async_setup(self) -> None:
        """Connect to the device during first refresh."""
        await self.hass.async_add_executor_job(self.device.connect)

    async def _async_update_data(self) -> dict:
        """Poll the device for current status."""
        try:
            return await self.hass.async_add_executor_job(self.device.query_status)
        except Exception as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err
