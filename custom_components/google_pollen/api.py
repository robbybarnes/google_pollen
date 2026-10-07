"""API client for Google Pollen API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import math
from typing import Any

import aiohttp

from .const import (
    API_BASE_URL,
    API_TIMEOUT_SECONDS,
    DEFAULT_FORECAST_DAYS,
    POLLEN_CATEGORIES,
    POLLEN_TYPES,
)


class GooglePollenApiError(Exception):
    """Base exception for Google Pollen API errors."""


class GooglePollenApiConnectionError(GooglePollenApiError):
    """Exception for connection errors."""


class GooglePollenApiAuthError(GooglePollenApiError):
    """Exception for authentication errors."""


class GooglePollenApiServiceError(GooglePollenApiError):
    """The Pollen API is disabled for the project."""


class GooglePollenApiQuotaError(GooglePollenApiError):
    """The project has exhausted its quota."""


class GooglePollenApiLocationError(GooglePollenApiError):
    """The requested location is invalid or unsupported."""


class GooglePollenApiPermissionError(GooglePollenApiError):
    """The project or API key lacks permission."""


class GooglePollenApiResponseError(GooglePollenApiError):
    """The API returned no usable forecast."""


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
    in_season: bool | None
    index_info: PollenIndex | None
    plant_description: PlantDescription | None


@dataclass
class PollenTypeInfo:
    """Representation of pollen type information."""

    code: str
    display_name: str
    in_season: bool | None
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
        self._api_key = api_key.strip()
        self._session = session

    async def async_get_forecast(
        self,
        latitude: float,
        longitude: float,
        days: int = DEFAULT_FORECAST_DAYS,
    ) -> PollenForecast:
        """Get pollen forecast for a location."""
        params = {
            "location.latitude": str(latitude),
            "location.longitude": str(longitude),
            "days": str(days),
            "plantsDescription": "true",
        }

        try:
            async with self._session.get(
                API_BASE_URL,
                params=params,
                # The key goes in a header rather than a query param so it
                # can't end up in URLs captured by logs or proxies.
                headers={"X-Goog-Api-Key": self._api_key},
                timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS),
            ) as response:
                if response.status == 200:
                    try:
                        data = await response.json()
                    except (ValueError, aiohttp.ContentTypeError) as err:
                        raise GooglePollenApiResponseError(
                            "The API returned an invalid forecast response"
                        ) from err
                    return self._parse_forecast(data)

                body_text = await response.text()
                raise self._response_error(response.status, body_text)

        except (aiohttp.ClientError, TimeoutError) as err:
            # Do not include provider text or request details in logs/UI errors.
            raise GooglePollenApiConnectionError(
                "Unable to connect to Google Pollen API"
            ) from err

    @staticmethod
    def _error_details(body_text: str) -> tuple[str, set[str]]:
        """Extract structured error codes without exposing provider messages."""
        try:
            payload = json.loads(body_text)
        except (ValueError, TypeError):
            return "", set()
        error = _mapping(_mapping(payload).get("error"))
        reasons = {
            reason
            for item in _list(error.get("details"))
            if (reason := _text(_mapping(item).get("reason")))
        }
        return _text(error.get("status")) or "", reasons

    @staticmethod
    def _is_auth_error(status: int, body_text: str) -> bool:
        """Only invalid/missing credentials should initiate reauthentication."""
        error_status, reasons = GooglePollenApiClient._error_details(body_text)
        return status == 401 or (
            status in (400, 403)
            and (
                error_status == "UNAUTHENTICATED"
                or bool(
                    reasons & {"API_KEY_INVALID", "API_KEY_MISSING", "API_KEY_EXPIRED"}
                )
            )
        )

    @staticmethod
    def _response_error(status: int, body_text: str) -> GooglePollenApiError:
        """Classify failures and return safe, actionable messages."""
        error_status, reasons = GooglePollenApiClient._error_details(body_text)
        if status == 429 or error_status == "RESOURCE_EXHAUSTED":
            return GooglePollenApiQuotaError(
                "Pollen API quota exhausted; check project quotas"
            )
        if "SERVICE_DISABLED" in reasons:
            return GooglePollenApiServiceError(
                "Enable the Pollen API in your Google Cloud project"
            )
        if GooglePollenApiClient._is_auth_error(status, body_text):
            return GooglePollenApiAuthError("The API key is invalid or expired")
        if status == 403:
            return GooglePollenApiPermissionError(
                "Check API key restrictions, project permissions, and billing"
            )
        if status in (400, 404):
            return GooglePollenApiLocationError(
                "Check the location coordinates and Pollen API coverage"
            )
        return GooglePollenApiError(
            f"Pollen API temporarily unavailable (HTTP {status})"
        )

    def _parse_forecast(self, data: dict[str, Any]) -> PollenForecast:
        """Parse the API response into a PollenForecast object."""
        data = _mapping(data)
        daily_info: dict[str, DailyPollenInfo] = {}
        for raw_day in _list(data.get("dailyInfo")):
            day_data = _mapping(raw_day)
            date_info = _mapping(day_data.get("date"))
            try:
                parts = [date_info.get(key) for key in ("year", "month", "day")]
                if any(type(part) is not int for part in parts):
                    continue
                date_str = date(*parts).isoformat()
            except (TypeError, ValueError):
                continue

            pollen_types: dict[str, PollenTypeInfo] = {}
            for raw_item in _list(day_data.get("pollenTypeInfo")):
                item = _mapping(raw_item)
                if item.get("code") in POLLEN_TYPES:
                    info = self._parse_pollen_type(item)
                    pollen_types[info.code] = info
            plants: dict[str, PlantInfo] = {}
            for raw_item in _list(day_data.get("plantInfo")):
                item = _mapping(raw_item)
                if _text(item.get("code")):
                    plant = self._parse_plant_info(item)
                    plants[plant.code] = plant
            if pollen_types or plants:
                daily_info.setdefault(
                    date_str, DailyPollenInfo(date_str, pollen_types, plants)
                )

        if not daily_info:
            raise GooglePollenApiResponseError(
                "No usable pollen data for this location"
            )
        return PollenForecast(
            region_code=_text(data.get("regionCode")) or "",
            daily_info=[daily_info[key] for key in sorted(daily_info)],
        )

    def _parse_pollen_type(self, data: dict[str, Any]) -> PollenTypeInfo:
        """Parse optional fields without substituting missing readings."""
        return PollenTypeInfo(
            code=data["code"],
            display_name=_text(data.get("displayName")) or "",
            in_season=_season(data.get("inSeason")),
            index_info=self._parse_index_info(data.get("indexInfo")),
            health_recommendations=[
                item
                for item in _list(data.get("healthRecommendations"))
                if isinstance(item, str)
            ],
        )

    def _parse_plant_info(self, data: dict[str, Any]) -> PlantInfo:
        """Parse plant info data."""
        description = _mapping(data.get("plantDescription"))
        return PlantInfo(
            code=data["code"],
            display_name=_text(data.get("displayName")) or "",
            in_season=_season(data.get("inSeason")),
            index_info=self._parse_index_info(data.get("indexInfo")),
            plant_description=self._parse_plant_description(description)
            if description
            else None,
        )

    def _parse_index_info(self, data: Any) -> PollenIndex | None:
        """Canonical categories derive from the validated numeric UPI."""
        if data is None:
            return None
        data = _mapping(data)
        value = data.get("value")
        if type(value) is not int or not 0 <= value <= 5:
            value = None
        return PollenIndex(
            code=_text(data.get("code")) or "",
            display_name=_text(data.get("displayName")) or "",
            value=value,
            category=POLLEN_CATEGORIES[value] if value is not None else None,
            description=_text(data.get("indexDescription")),
            color=_color_to_hex(data.get("color")),
        )

    def _parse_plant_description(self, data: dict[str, Any]) -> PlantDescription:
        """Parse plant description data."""
        return PlantDescription(
            plant_type=_text(data.get("type")),
            family=_text(data.get("family")),
            season=_text(data.get("season")),
            special_colors=_text(data.get("specialColors")),
            special_shapes=_text(data.get("specialShapes")),
            cross_reaction=_text(data.get("crossReaction")),
            picture=_text(data.get("picture")),
            picture_closeup=_text(data.get("pictureCloseup")),
        )


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _season(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _color_to_hex(data: dict[str, float] | None) -> str | None:
    """Convert Google's {red, green, blue} float color to a #RRGGBB string."""
    if not isinstance(data, dict):
        return None
    channels = []
    for key in ("red", "green", "blue"):
        value = data.get(key, 0.0)
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            return None
        clamped = max(0.0, min(1.0, float(value)))
        channels.append(round(clamped * 255))
    return "#{:02X}{:02X}{:02X}".format(*channels)
