"""Config flow for Midea ATW Heat Pump."""

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_DEVICE_ID, CONF_KEY, CONF_TOKEN, DEFAULT_PORT, DOMAIN
from .midea.device import MideaATWDevice

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_DEVICE_ID): vol.Coerce(int),
        vol.Required(CONF_TOKEN): str,
        vol.Required(CONF_KEY): str,
    }
)


class MideaHeatPumpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Midea ATW Heat Pump."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
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
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )
