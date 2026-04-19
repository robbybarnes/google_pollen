"""Data update coordinator for Google Pollen."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    GooglePollenApiClient,
    GooglePollenApiConnectionError,
    GooglePollenApiError,
    PollenForecast,
)
from .const import (
    CONF_UPDATE_INTERVAL_HOURS,
    DEFAULT_FORECAST_DAYS,
    DEFAULT_UPDATE_INTERVAL_HOURS,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class GooglePollenDataUpdateCoordinator(DataUpdateCoordinator[PollenForecast]):
    """Class to manage fetching Google Pollen data."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        client: GooglePollenApiClient,
        latitude: float,
        longitude: float,
    ) -> None:
        """Initialize the coordinator."""
        interval_hours = config_entry.options.get(
            CONF_UPDATE_INTERVAL_HOURS, DEFAULT_UPDATE_INTERVAL_HOURS
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_interval=timedelta(hours=interval_hours),
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
        except GooglePollenApiConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except GooglePollenApiError as err:
            raise UpdateFailed(f"Error fetching pollen data: {err}") from err

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
