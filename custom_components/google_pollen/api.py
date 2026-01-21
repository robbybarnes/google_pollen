"""API client for Google Pollen API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import API_BASE_URL, DEFAULT_FORECAST_DAYS

_LOGGER = logging.getLogger(__name__)


class GooglePollenApiError(Exception):
    """Base exception for Google Pollen API errors."""


class GooglePollenApiConnectionError(GooglePollenApiError):
    """Exception for connection errors."""


class GooglePollenApiAuthError(GooglePollenApiError):
    """Exception for authentication errors."""


@dataclass
class PollenIndex:
    """Representation of a pollen index."""

    code: str
    display_name: str
    value: int | None
    category: str | None
    description: str | None
    color: dict[str, float] | None


@dataclass
class PlantDescription:
    """Representation of a plant description."""

    plant_type: str | None
    family: str | None
    season: str | None
    special_colors: str | None
    special_shapes: str | None
    cross_reaction: str | None
    picture: str | None
    picture_closeup: str | None


@dataclass
class PlantInfo:
    """Representation of plant pollen information."""

    code: str
    display_name: str
    in_season: bool
    index_info: PollenIndex | None
    plant_description: PlantDescription | None


@dataclass
class PollenTypeInfo:
    """Representation of pollen type information."""

    code: str
    display_name: str
    in_season: bool
    index_info: PollenIndex | None
    health_recommendations: list[str]


@dataclass
class DailyPollenInfo:
    """Representation of daily pollen information."""

    date: str
    pollen_types: dict[str, PollenTypeInfo]
    plants: dict[str, PlantInfo]


@dataclass
class PollenForecast:
    """Representation of a pollen forecast."""

    region_code: str
    daily_info: list[DailyPollenInfo]


class GooglePollenApiClient:
    """Client for the Google Pollen API."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._api_key = api_key
        self._session = session

    async def async_get_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = DEFAULT_FORECAST_DAYS,
    ) -> PollenForecast:
        """Get pollen forecast for a location."""
        params = {
            "key": self._api_key,
            "location.latitude": str(latitude),
            "location.longitude": str(longitude),
            "days": str(days),
            "plantsDescription": "true",
        }

        try:
            async with self._session.get(
                API_BASE_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 401:
                    raise GooglePollenApiAuthError("Invalid API key")
                if response.status == 403:
                    raise GooglePollenApiAuthError(
                        "API key does not have access to Pollen API"
                    )
                if response.status != 200:
                    text = await response.text()
                    raise GooglePollenApiError(
                        f"API request failed with status {response.status}: {text}"
                    )

                data = await response.json()
                return self._parse_forecast(data)

        except aiohttp.ClientError as err:
            raise GooglePollenApiConnectionError(
                f"Error connecting to Google Pollen API: {err}"
            ) from err

    def _parse_forecast(self, data: dict[str, Any]) -> PollenForecast:
        """Parse the API response into a PollenForecast object."""
        region_code = data.get("regionCode", "")
        daily_info = []

        for day_data in data.get("dailyInfo", []):
            date_info = day_data.get("date", {})
            date_str = f"{date_info.get('year', '')}-{date_info.get('month', ''):02d}-{date_info.get('day', ''):02d}"

            # Parse pollen types
            pollen_types: dict[str, PollenTypeInfo] = {}
            for pollen_type_data in day_data.get("pollenTypeInfo", []):
                pollen_type = self._parse_pollen_type(pollen_type_data)
                pollen_types[pollen_type.code] = pollen_type

            # Parse plant info
            plants: dict[str, PlantInfo] = {}
            for plant_data in day_data.get("plantInfo", []):
                plant = self._parse_plant_info(plant_data)
                plants[plant.code] = plant

            daily_info.append(
                DailyPollenInfo(
                    date=date_str,
                    pollen_types=pollen_types,
                    plants=plants,
                )
            )

        return PollenForecast(
            region_code=region_code,
            daily_info=daily_info,
        )

    def _parse_pollen_type(self, data: dict[str, Any]) -> PollenTypeInfo:
        """Parse pollen type data."""
        index_info = None
        if "indexInfo" in data:
            index_info = self._parse_index_info(data["indexInfo"])

        return PollenTypeInfo(
            code=data.get("code", ""),
            display_name=data.get("displayName", ""),
            in_season=data.get("inSeason", False),
            index_info=index_info,
            health_recommendations=data.get("healthRecommendations", []),
        )

    def _parse_plant_info(self, data: dict[str, Any]) -> PlantInfo:
        """Parse plant info data."""
        index_info = None
        if "indexInfo" in data:
            index_info = self._parse_index_info(data["indexInfo"])

        plant_description = None
        if "plantDescription" in data:
            plant_description = self._parse_plant_description(data["plantDescription"])

        return PlantInfo(
            code=data.get("code", ""),
            display_name=data.get("displayName", ""),
            in_season=data.get("inSeason", False),
            index_info=index_info,
            plant_description=plant_description,
        )

    def _parse_index_info(self, data: dict[str, Any]) -> PollenIndex:
        """Parse index info data."""
        return PollenIndex(
            code=data.get("code", ""),
            display_name=data.get("displayName", ""),
            value=data.get("value"),
            category=data.get("category"),
            description=data.get("indexDescription"),
            color=data.get("color"),
        )

    def _parse_plant_description(self, data: dict[str, Any]) -> PlantDescription:
        """Parse plant description data."""
        return PlantDescription(
            plant_type=data.get("type"),
            family=data.get("family"),
            season=data.get("season"),
            special_colors=data.get("specialColors"),
            special_shapes=data.get("specialShapes"),
            cross_reaction=data.get("crossReaction"),
            picture=data.get("picture"),
            picture_closeup=data.get("pictureCloseup"),
        )

    async def async_validate_api_key(self) -> bool:
        """Validate the API key by making a test request."""
        try:
            # Use a known location for validation
            await self.async_get_forecast(
                latitude=37.7749,
                longitude=-122.4194,
                days=1,
            )
            return True
        except GooglePollenApiAuthError:
            return False
