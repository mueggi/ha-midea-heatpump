"""Tests for the MideaHeatPumpCoordinator retry and recovery logic."""

import asyncio
import logging
from unittest.mock import MagicMock, patch

import pytest


class FakeUpdateFailed(Exception):
    """Stand-in for homeassistant UpdateFailed."""
    pass


class FakeCoordinator:
    """Minimal replica of coordinator logic for testing without HA deps.

    Mirrors _async_update_data from coordinator.py exactly.
    """

    MAX_FAILURES = 3

    def __init__(self, device):
        self.device = device
        self._last_good_data = {}
        self._consecutive_failures = 0
        self.logger = logging.getLogger("test")

    async def _async_update_data(self) -> dict:
        try:
            data = self.device.query_status()
            if data:
                self._last_good_data = data
                self._consecutive_failures = 0
                return data
            raise ConnectionError("Empty response from device")
        except Exception as err:
            self._consecutive_failures += 1
            if self._consecutive_failures % self.MAX_FAILURES == 0:
                self.logger.warning(
                    "Device unreachable after %d attempts, forcing fresh reconnect: %s",
                    self._consecutive_failures,
                    err,
                )
                try:
                    self.device.connect()
                except Exception as reconn_err:
                    self.logger.debug("Reconnect failed: %s", reconn_err)
                raise FakeUpdateFailed(
                    f"Device unreachable after {self._consecutive_failures} attempts: {err}"
                ) from err
            self.logger.debug(
                "Poll failed (%d/%d), using cached data: %s",
                self._consecutive_failures,
                self.MAX_FAILURES,
                err,
            )
            return self._last_good_data


class TestCoordinatorUpdate:
    @pytest.mark.asyncio
    async def test_successful_poll(self):
        device = MagicMock()
        device.query_status.return_value = {"body_type": 0xC0, "power": True}
        coord = FakeCoordinator(device)

        result = await coord._async_update_data()
        assert result["body_type"] == 0xC0
        assert coord._consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_empty_response_treated_as_failure(self):
        device = MagicMock()
        device.query_status.return_value = {}
        coord = FakeCoordinator(device)
        coord._last_good_data = {"cached": True}

        result = await coord._async_update_data()
        assert result == {"cached": True}
        assert coord._consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_exception_returns_cached_data(self):
        device = MagicMock()
        device.query_status.side_effect = ConnectionError("timeout")
        coord = FakeCoordinator(device)
        coord._last_good_data = {"cached": True}

        result = await coord._async_update_data()
        assert result == {"cached": True}
        assert coord._consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_raises_after_max_failures(self):
        device = MagicMock()
        device.query_status.side_effect = ConnectionError("timeout")
        coord = FakeCoordinator(device)
        coord._last_good_data = {"cached": True}

        for i in range(coord.MAX_FAILURES - 1):
            result = await coord._async_update_data()
            assert result == {"cached": True}

        with pytest.raises(FakeUpdateFailed):
            await coord._async_update_data()

        assert coord._consecutive_failures == coord.MAX_FAILURES

    @pytest.mark.asyncio
    async def test_forces_reconnect_at_max_failures(self):
        device = MagicMock()
        device.query_status.side_effect = ConnectionError("timeout")
        coord = FakeCoordinator(device)

        for i in range(coord.MAX_FAILURES - 1):
            await coord._async_update_data()

        with pytest.raises(FakeUpdateFailed):
            await coord._async_update_data()

        device.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_reconnect_failure_still_raises_update_failed(self):
        device = MagicMock()
        device.query_status.side_effect = ConnectionError("timeout")
        device.connect.side_effect = OSError("still down")
        coord = FakeCoordinator(device)

        for i in range(coord.MAX_FAILURES - 1):
            await coord._async_update_data()

        with pytest.raises(FakeUpdateFailed):
            await coord._async_update_data()

        device.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_success_resets_failure_counter(self):
        device = MagicMock()
        device.query_status.side_effect = ConnectionError("timeout")
        coord = FakeCoordinator(device)

        await coord._async_update_data()
        await coord._async_update_data()
        assert coord._consecutive_failures == 2

        device.query_status.side_effect = None
        device.query_status.return_value = {"body_type": 0xC0}
        result = await coord._async_update_data()
        assert coord._consecutive_failures == 0
        assert result["body_type"] == 0xC0

    @pytest.mark.asyncio
    async def test_periodic_reconnect_every_max_failures(self):
        """Reconnect is attempted every MAX_FAILURES, not just once."""
        device = MagicMock()
        device.query_status.side_effect = ConnectionError("timeout")
        coord = FakeCoordinator(device)

        # First batch
        for i in range(coord.MAX_FAILURES - 1):
            await coord._async_update_data()
        with pytest.raises(FakeUpdateFailed):
            await coord._async_update_data()

        # Second batch
        for i in range(coord.MAX_FAILURES - 1):
            await coord._async_update_data()
        with pytest.raises(FakeUpdateFailed):
            await coord._async_update_data()

        assert device.connect.call_count == 2
        assert coord._consecutive_failures == coord.MAX_FAILURES * 2
