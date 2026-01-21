"""Data update coordinator for Google Pollen."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GooglePollenApiClient,
    GooglePollenApiConnectionError,
    GooglePollenApiError,
    PollenForecast,
)
from .const import DEFAULT_FORECAST_DAYS, DEFAULT_UPDATE_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class GooglePollenDataUpdateCoordinator(DataUpdateCoordinator[PollenForecast]):
    """Class to manage fetching Google Pollen data."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: GooglePollenApiClient,
        latitude: float,
        longitude: float,
        update_interval: timedelta = DEFAULT_UPDATE_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.client = client
        self.latitude = latitude
        self.longitude = longitude

    async def _async_update_data(self) -> PollenForecast:
        """Fetch data from API."""
        _LOGGER.debug("Fetching pollen data for %s, %s", self.latitude, self.longitude)
        try:
            forecast = await self.client.async_get_forecast(
                latitude=self.latitude,
                longitude=self.longitude,
                days=DEFAULT_FORECAST_DAYS,
            )
            _LOGGER.debug("Got forecast with region: %s", forecast.region_code)
            if forecast.daily_info:
                today = forecast.daily_info[0]
                _LOGGER.debug("Pollen types: %s", list(today.pollen_types.keys()))
                for code, info in today.pollen_types.items():
                    _LOGGER.debug(
                        "  %s: in_season=%s, has_index=%s",
                        code,
                        info.in_season,
                        info.index_info is not None,
                    )
            return forecast
        except GooglePollenApiConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except GooglePollenApiError as err:
            raise UpdateFailed(f"Error fetching pollen data: {err}") from err
