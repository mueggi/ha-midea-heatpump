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

    MAX_FAILURES = 3  # raise UpdateFailed after this many consecutive failures

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
        self._last_good_data: dict = {}
        self._consecutive_failures = 0

    async def _async_setup(self) -> None:
        """Connect to the device during first refresh."""
        await self.hass.async_add_executor_job(self.device.connect)

    async def _async_update_data(self) -> dict:
        """Poll the device for current status.

        Returns cached data on transient failures to avoid entity flickering.
        Only raises UpdateFailed after MAX_FAILURES consecutive failures.
        """
        try:
            data = await self.hass.async_add_executor_job(self.device.query_status)
            if data:
                self._last_good_data = data
                self._consecutive_failures = 0
                return data
            # Empty response — treat as transient failure
            raise ConnectionError("Empty response from device")
        except Exception as err:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.MAX_FAILURES:
                raise UpdateFailed(
                    f"Device unreachable after {self._consecutive_failures} attempts: {err}"
                ) from err
            _LOGGER.debug(
                "Poll failed (%d/%d), using cached data: %s",
                self._consecutive_failures,
                self.MAX_FAILURES,
                err,
            )
            return self._last_good_data
