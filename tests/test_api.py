"""Tests for the Google Pollen API client parsing."""

from __future__ import annotations

from unittest.mock import MagicMock

import aiohttp
import pytest

from custom_components.google_pollen.api import (
    GooglePollenApiClient,
    GooglePollenApiConnectionError,
    _color_to_hex,
)

INVALID_KEY_BODY = (
    '{"error": {"code": 400, "status": "INVALID_ARGUMENT",'
    ' "details": [{"reason": "API_KEY_INVALID"}]}}'
)


def _client(session: aiohttp.ClientSession | None = None) -> GooglePollenApiClient:
    return GooglePollenApiClient("dummy", session)


def test_parse_forecast_basic(forecast_json):
    """_parse_forecast extracts region, date, and pollen indices."""
    forecast = _client()._parse_forecast(forecast_json)

    assert forecast.region_code == "US"
    assert len(forecast.daily_info) == 2

    today = forecast.daily_info[0]
    assert today.date == "2026-04-19"

    grass = today.pollen_types["GRASS"]
    assert grass.in_season is True
    assert grass.index_info.value == 3
    assert grass.index_info.category == "Moderate"
    assert grass.health_recommendations == ["Close windows"]

    weed = today.pollen_types["WEED"]
    assert weed.in_season is False
    assert weed.index_info is None


def test_parse_forecast_skips_incomplete_dates():
    """Regression: days missing year/month/day must not raise."""
    payload = {
        "regionCode": "US",
        "dailyInfo": [
            {"date": {"year": 2026, "month": 4}, "pollenTypeInfo": []},
            {"date": {}, "pollenTypeInfo": []},
            {
                "date": {"year": 2026, "month": 4, "day": 19},
                "pollenTypeInfo": [],
            },
        ],
    }

    forecast = _client()._parse_forecast(payload)

    assert len(forecast.daily_info) == 1
    assert forecast.daily_info[0].date == "2026-04-19"


def test_is_auth_error_detects_api_key_invalid():
    """Regression: Google returns 400 w/ API_KEY_INVALID for bad keys."""
    assert GooglePollenApiClient._is_auth_error(400, INVALID_KEY_BODY) is True


def test_is_auth_error_401_403():
    """401 and 403 always count as auth errors."""
    assert GooglePollenApiClient._is_auth_error(401, "") is True
    assert GooglePollenApiClient._is_auth_error(403, "") is True


def test_is_auth_error_ignores_other_400():
    """Non-auth 400s (e.g. bad coords) must NOT be classified as auth errors."""
    body = '{"error": {"status": "INVALID_ARGUMENT", "message": "bad latitude"}}'
    assert GooglePollenApiClient._is_auth_error(400, body) is False


def test_is_auth_error_ignores_500():
    """Server errors are not auth errors."""
    assert GooglePollenApiClient._is_auth_error(500, "oops") is False


def test_color_parsed_to_hex(forecast_json):
    """PollenIndex.color is exposed as a #RRGGBB string."""
    forecast = _client()._parse_forecast(forecast_json)
    grass = forecast.daily_info[0].pollen_types["GRASS"]
    # red=1.0, green=0.8, blue=0.0 -> 255, 204, 0
    assert grass.index_info.color == "#FFCC00"


def test_color_to_hex_defaults_missing_channels():
    """Google omits zero channels; default them to 0.0."""
    assert _color_to_hex({"red": 1.0}) == "#FF0000"
    assert _color_to_hex({}) == "#000000"
    assert _color_to_hex(None) is None


def test_color_to_hex_clamps_out_of_range():
    """Values outside [0, 1] are clamped before scaling."""
    assert _color_to_hex({"red": 2.0, "green": -1.0, "blue": 0.5}) == "#FF0080"


async def test_timeout_classified_as_connection_error():
    """asyncio.TimeoutError surfaces as a connection error, not a generic error."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.side_effect = TimeoutError()
    client = _client(session)

    with pytest.raises(GooglePollenApiConnectionError):
        await client.async_get_forecast(latitude=0.0, longitude=0.0)


async def test_client_error_classified_as_connection_error():
    """aiohttp.ClientError surfaces as a connection error."""
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.side_effect = aiohttp.ClientError("dns")
    client = _client(session)

    with pytest.raises(GooglePollenApiConnectionError):
        await client.async_get_forecast(latitude=0.0, longitude=0.0)
