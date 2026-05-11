"""API client for Google Pollen API."""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
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
    color: str | None


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
                if response.status == 200:
                    data = await response.json()
                    return self._parse_forecast(data)

                body_text = await response.text()
                if self._is_auth_error(response.status, body_text):
                    raise GooglePollenApiAuthError(
                        f"Authentication failed ({response.status}): {body_text}"
                    )
                raise GooglePollenApiError(
                    f"API request failed with status {response.status}: {body_text}"
                )

        except (aiohttp.ClientError, TimeoutError) as err:
            raise GooglePollenApiConnectionError(
                f"Error connecting to Google Pollen API: {err}"
            ) from err

    @staticmethod
    def _is_auth_error(status: int, body_text: str) -> bool:
        """Identify auth/permission failures across 400/401/403 responses."""
        if status in (401, 403):
            return True
        if status != 400:
            return False
        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError:
            return False
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if error.get("status") in {"UNAUTHENTICATED", "PERMISSION_DENIED"}:
            return True
        for detail in error.get("details", []) or []:
            if isinstance(detail, dict) and detail.get("reason") in {
                "API_KEY_INVALID",
                "API_KEY_MISSING",
                "SERVICE_DISABLED",
            }:
                return True
        return False

    def _parse_forecast(self, data: dict[str, Any]) -> PollenForecast:
        """Parse the API response into a PollenForecast object."""
        region_code = data.get("regionCode", "")
        daily_info = []

        for day_data in data.get("dailyInfo", []):
            date_info = day_data.get("date", {})
            year = date_info.get("year")
            month = date_info.get("month")
            day = date_info.get("day")
            if not (year and month and day):
                _LOGGER.debug("Skipping day with incomplete date: %s", date_info)
                continue
            date_str = f"{year:04d}-{month:02d}-{day:02d}"

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
            color=_color_to_hex(data.get("color")),
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


def _color_to_hex(data: dict[str, float] | None) -> str | None:
    """Convert Google's {red, green, blue} float color to a #RRGGBB string."""
    if data is None:
        return None
    channels = []
    for key in ("red", "green", "blue"):
        value = data.get(key, 0.0) or 0.0
        clamped = max(0.0, min(1.0, float(value)))
        channels.append(round(clamped * 255))
    return "#{:02X}{:02X}{:02X}".format(*channels)
