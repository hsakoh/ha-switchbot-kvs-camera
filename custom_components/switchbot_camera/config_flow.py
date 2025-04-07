"""Config flow for the SwitchBot KVSCamera integration."""

from __future__ import annotations

import logging
from typing import Any
import uuid

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import APPLICATION_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector

from .api_client.api_client import SwitchBotApiClient
from .api_client.exceptions import ApiError
from .const import (
    DOMAIN,
    RESOLUTION,
    RESOLUTION_HD,
    RESOLUTION_SD,
    SNAPSHOT_ENABLE,
    SNAPSHOT_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def validate_input(
    hass: HomeAssistant, hardware_id: str, data: dict[str, Any]
) -> SwitchBotApiClient.ApiCredential:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    client = SwitchBotApiClient(
        http_client_session=async_get_clientsession(hass),
        device_id=hardware_id,
        device_name=APPLICATION_NAME,
        model=f"{DOMAIN}-integration",
    )

    try:
        api_credential = await client.login(data[CONF_USERNAME], data[CONF_PASSWORD])
    except ApiError as err:
        raise InvalidAuth from err

    return api_credential


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBot KVSCamera."""

    VERSION = 1

    device_id: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if not self.device_id:
                self.device_id = str(uuid.uuid4())
            try:
                api_credential = await validate_input(
                    self.hass, self.device_id, user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(api_credential.user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=api_credential.email, data=api_credential.__dict__
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add reconfigure step to allow to reconfigure a config entry."""
        errors: dict[str, str] = {}
        config_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        if not self.device_id:
            self.device_id = config_entry.data["device_id"]
            assert self.device_id

        if user_input is not None:
            try:
                api_credential = await validate_input(
                    self.hass, self.device_id, user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    config_entry,
                    unique_id=config_entry.unique_id,
                    data=api_credential.__dict__,
                    reason="reconfigure_successful",
                )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class OptionsFlowHandler(OptionsFlow):
    """Handles the options flow."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            options = self.config_entry.options | user_input
            return self.async_create_entry(title="", data=options)
        data_schema = vol.Schema(
            {
                vol.Required(
                    RESOLUTION,
                    default=self.options.get(RESOLUTION, RESOLUTION_HD),
                ): selector(
                    {
                        "select": {
                            "options": [RESOLUTION_HD, RESOLUTION_SD],
                            "mode": "dropdown",
                            "sort": False,
                        }
                    }
                ),
                vol.Required(
                    SNAPSHOT_ENABLE, default=self.options.get(SNAPSHOT_ENABLE, False)
                ): bool,
                vol.Required(
                    SNAPSHOT_INTERVAL,
                    default=self.options.get(SNAPSHOT_INTERVAL, 120),
                ): (vol.All(vol.Coerce(int), vol.Clamp(min=60))),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
