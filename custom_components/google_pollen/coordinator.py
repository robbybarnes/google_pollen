"""Data update coordinator for Google Pollen."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import (
    GooglePollenApiAuthError,
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
    POLLEN_TYPES,
)
from .forecast import forecast_day, future_forecast

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
        self.last_successful_update: datetime | None = None
        self.client = client
        self.latitude = latitude
        self.longitude = longitude
        self.attributes_by_type: dict[str, dict[str, Any]] = {}
        self.device_info = DeviceInfo(
            identifiers={(DOMAIN, config_entry.entry_id)},
            name=config_entry.title,
            manufacturer="Google",
            model="Pollen API",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://developers.google.com/maps/documentation/pollen",
        )

    async def _async_update_data(self) -> PollenForecast:
        """Fetch data from API."""
        _LOGGER.debug("Fetching pollen forecast")
        try:
            forecast = await self.client.async_get_forecast(
                latitude=self.latitude,
                longitude=self.longitude,
                days=DEFAULT_FORECAST_DAYS,
            )
        except GooglePollenApiAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
        except GooglePollenApiConnectionError as err:
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except GooglePollenApiError as err:
            raise UpdateFailed(f"Error fetching pollen data: {err}") from err

        if forecast_day(forecast) is None:
            raise UpdateFailed("No pollen forecast for the current UTC date")
        self.last_successful_update = dt_util.utcnow()
        self.attributes_by_type = _build_attributes_by_type(forecast)
        return forecast

    @callback
    def async_handle_utc_midnight(self, now: datetime) -> None:
        """Advance cached daily readings without fetching or changing poll timing."""
        if self.data is not None:
            self.attributes_by_type = _build_attributes_by_type(self.data, now.date())
            self.async_update_listeners()

    @property
    def freshness_attributes(self) -> dict[str, Any]:
        """Expose the date of the reading and the last successful network refresh."""
        day = forecast_day(self.data) if self.data else None
        return {
            "forecast_date": day.date if day else None,
            "last_successful_update": (
                self.last_successful_update.isoformat()
                if self.last_successful_update
                else None
            ),
        }


def _build_attributes_by_type(
    forecast: PollenForecast,
    current_date: date | None = None,
) -> dict[str, dict[str, Any]]:
    """Precompute the per-pollen-type attribute payload for sensors."""
    today = forecast_day(forecast, current_date)
    plants_by_type = _bucket_plants_by_type(today.plants) if today else {}

    result: dict[str, dict[str, Any]] = {}
    for code in POLLEN_TYPES:
        info = today.pollen_types.get(code) if today else None
        attrs: dict[str, Any] = {}
        if info is not None:
            attrs["in_season"] = info.in_season

        if info and info.health_recommendations:
            attrs["health_recommendations"] = info.health_recommendations
        if info and info.index_info:
            attrs["index_description"] = info.index_info.description
            if info.index_info.color:
                attrs["color"] = info.index_info.color

        in_season_plants = plants_by_type.get(code, [])
        if in_season_plants:
            attrs["in_season_plants"] = in_season_plants

        forecast_days = future_forecast(forecast, code, today=current_date)
        if forecast_days:
            attrs["forecast"] = forecast_days

        result[code] = attrs
    return result


def _bucket_plants_by_type(plants: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Group in-season plants by their parent pollen type code."""
    buckets: dict[str, list[dict[str, Any]]] = {}
    for plant in plants.values():
        if not plant.in_season:
            continue
        description = plant.plant_description
        plant_type = description.plant_type if description else None
        if not plant_type:
            _LOGGER.debug("Skipping plant with no parent type: %s", plant.code)
            continue
        buckets.setdefault(plant_type, []).append(
            {
                "code": plant.code,
                "display_name": plant.display_name,
                "family": description.family if description else None,
                "season": description.season if description else None,
                "cross_reaction": description.cross_reaction if description else None,
            }
        )
    return buckets
