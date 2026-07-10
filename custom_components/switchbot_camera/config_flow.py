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
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import selector

from .api_client.api_client import SwitchBotApiClient
from .api_client.exceptions import ApiError, MfaRequired, MfaTokenExpired
from .const import (
    DOMAIN,
    RESOLUTION,
    RESOLUTION_HD,
    RESOLUTION_SD,
    SNAPSHOT_ENABLE,
    SNAPSHOT_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

CONF_VERIFY_CODE = "verify_code"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

STEP_MFA_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_VERIFY_CODE): str,
    }
)


def _create_client(hass: HomeAssistant, device_id: str) -> SwitchBotApiClient:
    """Build an API client bound to the integration's device identity."""
    return SwitchBotApiClient(
        http_client_session=async_get_clientsession(hass),
        device_id=device_id,
        device_name=APPLICATION_NAME,
        model=f"{DOMAIN}-integration",
    )


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SwitchBot KVSCamera."""

    VERSION = 1

    device_id: str | None = None
    _client: SwitchBotApiClient | None = None
    _mfa_token: str | None = None
    _reconfigure_entry: ConfigEntry | None = None

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
            self._client = _create_client(self.hass, self.device_id)
            try:
                api_credential = await self._client.login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except MfaRequired as err:
                mfa_result = await self._async_start_mfa(err.mfa_token, errors)
                if mfa_result is not None:
                    return mfa_result
            except ApiError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
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
        self._reconfigure_entry = config_entry
        if not self.device_id:
            self.device_id = config_entry.data["device_id"]
            assert self.device_id

        if user_input is not None:
            self._client = _create_client(self.hass, self.device_id)
            try:
                api_credential = await self._client.login(
                    user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
                )
            except MfaRequired as err:
                mfa_result = await self._async_start_mfa(err.mfa_token, errors)
                if mfa_result is not None:
                    return mfa_result
            except ApiError:
                errors["base"] = "invalid_auth"
            except Exception:  # noqa: BLE001
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

    async def _async_start_mfa(
        self, mfa_token: str, errors: dict[str, str]
    ) -> ConfigFlowResult | None:
        """Request an email code and show the MFA form.

        Returns the MFA form to render, or ``None`` to let the caller re-render its
        own form with ``errors`` populated (code send failed).
        """
        assert self._client is not None
        self._mfa_token = mfa_token
        try:
            await self._client.send_mfa_code(mfa_token)
        except MfaTokenExpired:
            errors["base"] = "mfa_token_expired"
            return None
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Failed to send MFA code")
            errors["base"] = "cannot_connect"
            return None
        return self.async_show_form(
            step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA
        )

    async def async_step_mfa(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Verify the two-factor code and finish the (re)configuration."""
        errors: dict[str, str] = {}
        if user_input is not None:
            assert self._client is not None
            assert self._mfa_token is not None
            try:
                api_credential = await self._client.login_mfa(
                    self._mfa_token, user_input[CONF_VERIFY_CODE]
                )
            except MfaTokenExpired:
                errors["base"] = "mfa_token_expired"
            except ApiError:
                errors["base"] = "invalid_mfa_code"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                if self._reconfigure_entry is not None:
                    return self.async_update_reload_and_abort(
                        self._reconfigure_entry,
                        unique_id=self._reconfigure_entry.unique_id,
                        data=api_credential.__dict__,
                        reason="reconfigure_successful",
                    )
                await self.async_set_unique_id(api_credential.user_id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=api_credential.email, data=api_credential.__dict__
                )

        return self.async_show_form(
            step_id="mfa", data_schema=STEP_MFA_DATA_SCHEMA, errors=errors
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
