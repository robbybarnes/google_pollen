"""Config flow for Google Pollen integration."""

from __future__ import annotations

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
                f"{user_input[CONF_LATITUDE]}_{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            errors = await _validate_connection(self.hass, user_input)
            if not errors:
                title = (
                    f"Pollen ({user_input[CONF_LATITUDE]:.2f}, "
                    f"{user_input[CONF_LONGITUDE]:.2f})"
                )
                return self.async_create_entry(title=title, data=user_input)

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
        """Handle a reconfigure flow."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(
                f"{user_input[CONF_LATITUDE]}_{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_mismatch()

            errors = await _validate_connection(self.hass, user_input)
            if not errors:
                return self.async_update_reload_and_abort(entry, data=user_input)

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
