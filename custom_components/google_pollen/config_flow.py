"""Config flow for Google Pollen integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    GooglePollenApiAuthError,
    GooglePollenApiClient,
    GooglePollenApiConnectionError,
)
from .const import CONF_API_KEY, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GooglePollenConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Pollen."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Check if already configured with same location
            await self.async_set_unique_id(
                f"{user_input[CONF_LATITUDE]}_{user_input[CONF_LONGITUDE]}"
            )
            self._abort_if_unique_id_configured()

            # Validate the API key
            session = async_get_clientsession(self.hass)
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
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Create a nice title based on location
                title = f"Pollen ({user_input[CONF_LATITUDE]:.2f}, {user_input[CONF_LONGITUDE]:.2f})"
                return self.async_create_entry(title=title, data=user_input)

        # Pre-fill with Home Assistant's configured location
        suggested_latitude = self.hass.config.latitude
        suggested_longitude = self.hass.config.longitude

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_KEY): str,
                vol.Required(
                    CONF_LATITUDE, default=suggested_latitude
                ): vol.Coerce(float),
                vol.Required(
                    CONF_LONGITUDE, default=suggested_longitude
                ): vol.Coerce(float),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )
