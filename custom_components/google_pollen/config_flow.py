"""Config flow for Google Pollen integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import (
    GooglePollenApiAuthError,
    GooglePollenApiClient,
    GooglePollenApiConnectionError,
)
from .const import (
    CONF_API_KEY,
    CONF_UPDATE_INTERVAL_HOURS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _unique_id(latitude: float, longitude: float) -> str:
    """Build the per-location unique id."""
    return f"{latitude}_{longitude}"


async def _validate_connection(hass, user_input: dict[str, Any]) -> dict[str, str]:
    """Return an `errors` dict; empty on success."""
    errors: dict[str, str] = {}
    session = async_get_clientsession(hass)
    client = GooglePollenApiClient(user_input[CONF_API_KEY], session)

    try:
        await client.async_get_forecast(
            latitude=user_input[CONF_LATITUDE],
            longitude=user_input[CONF_LONGITUDE],
            days=1,
        )
    except GooglePollenApiAuthError:
        errors["base"] = "invalid_auth"
    except GooglePollenApiConnectionError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected exception validating Google Pollen API")
        errors["base"] = "unknown"

    return errors


def _build_schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the user/reconfigure schema with pre-filled defaults."""
    return vol.Schema(
        {
            vol.Required(CONF_API_KEY, default=defaults.get(CONF_API_KEY, "")): str,
            vol.Required(CONF_LATITUDE, default=defaults[CONF_LATITUDE]): vol.Coerce(
                float
            ),
            vol.Required(CONF_LONGITUDE, default=defaults[CONF_LONGITUDE]): vol.Coerce(
                float
            ),
        }
    )


class GooglePollenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Pollen."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> OptionsFlow:
        """Return the options flow handler."""
        return GooglePollenOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                _unique_id(user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE])
            )
            self._abort_if_unique_id_configured()

            errors = await _validate_connection(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title="Google Pollen", data=user_input)

        defaults = {
            CONF_API_KEY: (user_input or {}).get(CONF_API_KEY, ""),
            CONF_LATITUDE: (user_input or {}).get(
                CONF_LATITUDE, self.hass.config.latitude
            ),
            CONF_LONGITUDE: (user_input or {}).get(
                CONF_LONGITUDE, self.hass.config.longitude
            ),
        }

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(defaults),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfigure flow.

        Allows changing API key and/or location. Aborts if the new location
        collides with a different existing entry.
        """
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            new_unique_id = _unique_id(
                user_input[CONF_LATITUDE], user_input[CONF_LONGITUDE]
            )
            collision = next(
                (
                    other
                    for other in self._async_current_entries()
                    if other.entry_id != entry.entry_id
                    and other.unique_id == new_unique_id
                ),
                None,
            )
            if collision is not None:
                return self.async_abort(reason="already_configured")

            errors = await _validate_connection(self.hass, user_input)
            if not errors:
                return self.async_update_reload_and_abort(
                    entry, data=user_input, unique_id=new_unique_id
                )

        defaults = {
            CONF_API_KEY: (user_input or entry.data).get(CONF_API_KEY, ""),
            CONF_LATITUDE: (user_input or entry.data)[CONF_LATITUDE],
            CONF_LONGITUDE: (user_input or entry.data)[CONF_LONGITUDE],
        }

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_schema(defaults),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        """Handle a reauth flow when the API key stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt the user for a new API key."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            merged = {**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]}
            errors = await _validate_connection(self.hass, merged)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=merged)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_API_KEY): str}),
            errors=errors,
        )


class GooglePollenOptionsFlow(OptionsFlow):
    """Handle an options flow for Google Pollen."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL_HOURS, DEFAULT_UPDATE_INTERVAL_HOURS
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UPDATE_INTERVAL_HOURS, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=24)
                    ),
                }
            ),
        )
