"""Tests for the Google Pollen API client parsing."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.google_pollen.api import (
    GooglePollenApiClient,
    GooglePollenApiConnectionError,
    GooglePollenApiError,
    GooglePollenApiResponseError,
    _color_to_hex,
)
from custom_components.google_pollen.const import POLLEN_CATEGORIES

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
                "pollenTypeInfo": [{"code": "GRASS", "inSeason": False}],
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
    """Only unauthenticated credentials initiate reauthentication."""
    assert GooglePollenApiClient._is_auth_error(401, "") is True
    assert GooglePollenApiClient._is_auth_error(403, "") is False


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


@pytest.mark.parametrize(
    ("status", "error_status", "reason", "error_type"),
    [
        (400, "INVALID_ARGUMENT", "API_KEY_INVALID", "GooglePollenApiAuthError"),
        (401, "UNAUTHENTICATED", None, "GooglePollenApiAuthError"),
        (403, "PERMISSION_DENIED", "SERVICE_DISABLED", "GooglePollenApiServiceError"),
        (
            403,
            "PERMISSION_DENIED",
            "API_KEY_IP_ADDRESS_BLOCKED",
            "GooglePollenApiPermissionError",
        ),
        (403, "RESOURCE_EXHAUSTED", None, "GooglePollenApiQuotaError"),
        (429, "RESOURCE_EXHAUSTED", None, "GooglePollenApiQuotaError"),
        (400, "INVALID_ARGUMENT", None, "GooglePollenApiLocationError"),
        (404, "NOT_FOUND", None, "GooglePollenApiLocationError"),
        (503, "UNAVAILABLE", None, "GooglePollenApiError"),
    ],
)
async def test_http_errors_are_actionable_and_do_not_echo_provider_data(
    status, error_status, reason, error_type
):
    """HTTP failures use structured codes, never private provider messages."""

    response = AsyncMock(spec=aiohttp.ClientResponse)
    response.status = status
    response.text.return_value = json.dumps(
        {
            "error": {
                "status": error_status,
                "message": "secret-key at 37.7749",
                "details": [{"reason": reason}] if reason else [],
            }
        }
    )
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value.__aenter__.return_value = response
    client = GooglePollenApiClient("secret-key", session)
    with pytest.raises(GooglePollenApiError) as exc:
        await client.async_get_forecast(37.7749, -122.4194)
    assert type(exc.value).__name__ == error_type
    assert "secret-key" not in str(exc.value)
    assert "37.7749" not in str(exc.value)
    kwargs = session.get.call_args.kwargs
    assert kwargs["headers"] == {"X-Goog-Api-Key": "secret-key"}
    assert "key" not in kwargs["params"]


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"dailyInfo": None},
        {"dailyInfo": [None, {"date": {"year": 2026, "month": 2, "day": 30}}]},
    ],
)
def test_unusable_forecasts_are_rejected(payload):
    """Malformed/empty successful responses cannot become a successful refresh."""

    with pytest.raises(GooglePollenApiResponseError):
        _client()._parse_forecast(payload)


@pytest.mark.parametrize("value", [None, -1, 6, True, "3", 2.5])
def test_invalid_index_remains_unknown(forecast_json, value):
    """Invalid readings never become numeric zero or arbitrary enum states."""
    index = forecast_json["dailyInfo"][0]["pollenTypeInfo"][0]["indexInfo"]
    index["value"] = value
    index["category"] = "Very low"
    parsed = _client()._parse_forecast(forecast_json)
    info = parsed.daily_info[0].pollen_types["GRASS"].index_info
    assert info.value is None
    assert info.category is None


@pytest.mark.parametrize("value", range(6))
def test_category_is_normalized_from_numeric_index(forecast_json, value):
    """Provider capitalization and mismatching labels cannot break enum sensors."""

    index = forecast_json["dailyInfo"][0]["pollenTypeInfo"][0]["indexInfo"]
    index.update(value=value, category="unexpected category")
    parsed = _client()._parse_forecast(forecast_json)
    assert (
        parsed.daily_info[0].pollen_types["GRASS"].index_info.category
        == POLLEN_CATEGORIES[value]
    )


def test_optional_null_fields_and_sorted_dates(forecast_json):
    """Optional nulls and unordered/duplicate dates do not break valid days."""
    first = forecast_json["dailyInfo"][0]
    first["pollenTypeInfo"][0].update(healthRecommendations=None, indexInfo=None)
    first["plantInfo"][0].update(plantDescription=None, inSeason=None)
    forecast_json["dailyInfo"] = [forecast_json["dailyInfo"][1], None, first, first]
    parsed = _client()._parse_forecast(forecast_json)
    assert [day.date for day in parsed.daily_info] == ["2026-04-19", "2026-04-20"]
    assert parsed.daily_info[0].pollen_types["GRASS"].health_recommendations == []
    assert parsed.daily_info[0].plants["GRAMINALES"].in_season is None


@pytest.mark.parametrize(
    "body",
    [
        "not JSON",
        "null",
        "[]",
        '{"error": null}',
        '{"error": {"details": [null, "invalid"]}}',
    ],
)
def test_malformed_error_bodies_do_not_crash(body):
    """Provider error formatting must not cause an unexpected exception."""
    assert GooglePollenApiClient._is_auth_error(403, body) is False


async def test_successful_http_response_is_parsed(forecast_json):
    """Successful HTTP responses run through numeric/category validation."""
    response = AsyncMock(spec=aiohttp.ClientResponse)
    response.status = 200
    response.json.return_value = forecast_json
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value.__aenter__.return_value = response
    forecast = await _client(session).async_get_forecast(0.0, 0.0)
    assert forecast.daily_info[0].pollen_types["TREE"].index_info.category == "High"


async def test_invalid_json_is_a_response_failure():
    """An invalid success body gets an actionable no-data error."""
    response = AsyncMock(spec=aiohttp.ClientResponse)
    response.status = 200
    response.json.side_effect = ValueError("not JSON")
    session = MagicMock(spec=aiohttp.ClientSession)
    session.get.return_value.__aenter__.return_value = response
    with pytest.raises(GooglePollenApiResponseError):
        await _client(session).async_get_forecast(0.0, 0.0)
