"""Config flow for Midea ATW Heat Pump."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import (
    CLOUD_SERVERS,
    CONF_DEVICE_ID,
    CONF_EMAIL,
    CONF_KEY,
    CONF_PASSWORD,
    CONF_SERVER,
    CONF_TOKEN,
    DEFAULT_PORT,
    DOMAIN,
    SERVER_NETHOME,
    SERVER_SMARTHOME,
)
from .midea.device import MideaATWDevice

_LOGGER = logging.getLogger(__name__)

STEP_MANUAL_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_DEVICE_ID): vol.Coerce(int),
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_KEY): str,
    }
)

STEP_CLOUD_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_SERVER, default=SERVER_SMARTHOME): vol.In(CLOUD_SERVERS),
    }
)

STEP_NETWORK_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)

DEVICE_TYPE_C3 = 0xC3


class MideaHeatPumpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Midea ATW Heat Pump."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._cloud_devices: list[dict] = []
        self._selected_device: dict = {}
        self._token: str = ""
        self._key: str = ""

    async def async_step_user(self, user_input=None):
        """Handle the initial step — choose setup method."""
        if user_input is not None:
            if user_input["setup_method"] == "cloud":
                return await self.async_step_cloud()
            return await self.async_step_manual()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("setup_method", default="cloud"): vol.In(
                        {"cloud": "Cloud Login", "manual": "Manual Setup"}
                    ),
                }
            ),
        )

    async def async_step_cloud(self, user_input=None):
        """Handle cloud credential entry and login."""
        errors = {}

        if user_input is not None:
            try:
                cloud = self._create_cloud_client(
                    server=user_input[CONF_SERVER],
                    email=user_input[CONF_EMAIL],
                    password=user_input[CONF_PASSWORD],
                )
                await cloud.login()

                # Fetch device list via internal API
                response = await cloud._api_request(
                    "/v1/appliance/user/list/get",
                    cloud._build_request_body({}),
                )
                all_devices = response.get("list", [])

                # Filter to 0xC3 (ATW heat pump) devices
                self._cloud_devices = []
                for dev in all_devices:
                    try:
                        dev_type = int(str(dev.get("type", "0")), 0)
                    except (ValueError, TypeError):
                        continue
                    if dev_type == DEVICE_TYPE_C3:
                        self._cloud_devices.append(dev)

                if not self._cloud_devices:
                    errors["base"] = "no_devices"
                else:
                    # Store cloud client for token retrieval
                    self._cloud = cloud
                    return await self.async_step_select_device()

            except Exception:
                _LOGGER.exception("Cloud login failed")
                errors["base"] = "login_failed"

        return self.async_show_form(
            step_id="cloud",
            data_schema=STEP_CLOUD_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    def _create_cloud_client(server: str, email: str, password: str):
        """Create the appropriate cloud client."""
        from msmart.cloud import NetHomePlusCloud, SmartHomeCloud

        if server == SERVER_NETHOME:
            return NetHomePlusCloud(account=email, password=password)
        return SmartHomeCloud(account=email, password=password)

    async def async_step_select_device(self, user_input=None):
        """Handle device selection from cloud device list."""
        errors = {}

        if user_input is not None:
            device_id_str = user_input["device"]
            # Find the selected device
            for dev in self._cloud_devices:
                if str(dev.get("id")) == device_id_str:
                    self._selected_device = dev
                    break

            # Retrieve token and key
            try:
                from msmart.lan import Security

                device_id = int(device_id_str)
                # Try both endians like msmart-ng discovery does
                token = None
                key = None
                for endian in ("little", "big"):
                    try:
                        udpid = Security.udpid(
                            device_id.to_bytes(6, endian)
                        ).hex()
                        token, key = await self._cloud.get_token(udpid)
                        break
                    except Exception:
                        continue

                if token and key:
                    self._token = token
                    self._key = key
                    return await self.async_step_network()

                errors["base"] = "token_failed"

            except Exception:
                _LOGGER.exception("Token retrieval failed")
                errors["base"] = "token_failed"

        # Build device dropdown options
        device_options = {}
        for dev in self._cloud_devices:
            dev_id = str(dev.get("id", ""))
            dev_name = dev.get("name", "Unknown")
            device_options[dev_id] = f"{dev_name} ({dev_id})"

        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema(
                {
                    vol.Required("device"): vol.In(device_options),
                }
            ),
            errors=errors,
        )

    async def async_step_network(self, user_input=None):
        """Handle LAN connection details entry."""
        errors = {}

        if user_input is not None:
            device_id = int(self._selected_device.get("id"))
            try:
                device = MideaATWDevice(
                    ip=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    device_id=device_id,
                    token=self._token,
                    key=self._key,
                )
                await self.hass.async_add_executor_job(device.connect)
                data = await self.hass.async_add_executor_job(device.query_status)
                await self.hass.async_add_executor_job(device.close)

                if not data:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(str(device_id))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=self._selected_device.get(
                            "name", "Midea ATW Heat Pump"
                        ),
                        data={
                            CONF_HOST: user_input[CONF_HOST],
                            CONF_PORT: user_input[CONF_PORT],
                            CONF_DEVICE_ID: device_id,
                            CONF_TOKEN: self._token,
                            CONF_KEY: self._key,
                        },
                    )
            except Exception:
                _LOGGER.exception("Failed to connect to Midea heat pump")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="network",
            data_schema=STEP_NETWORK_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_manual(self, user_input=None):
        """Handle manual entry (existing flow)."""
        errors = {}

        if user_input is not None:
            try:
                device = MideaATWDevice(
                    ip=user_input[CONF_HOST],
                    port=user_input[CONF_PORT],
                    device_id=user_input[CONF_DEVICE_ID],
                    token=user_input[CONF_TOKEN],
                    key=user_input[CONF_KEY],
                )
                await self.hass.async_add_executor_job(device.connect)
                data = await self.hass.async_add_executor_job(device.query_status)
                await self.hass.async_add_executor_job(device.close)

                if not data:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(str(user_input[CONF_DEVICE_ID]))
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title="Midea ATW Heat Pump",
                        data=user_input,
                    )
            except Exception:
                _LOGGER.exception("Failed to connect to Midea heat pump")
                errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="manual",
            data_schema=STEP_MANUAL_DATA_SCHEMA,
            errors=errors,
        )
