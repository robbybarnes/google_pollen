"""Shared fixtures for Google Pollen tests."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.google_pollen.api import GooglePollenApiClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically enable loading of custom integrations in all tests."""
    return


@pytest.fixture
def forecast_json() -> dict:
    """Load the canned forecast fixture."""
    with (FIXTURES_DIR / "forecast.json").open() as fp:
        return json.load(fp)


@pytest.fixture
def mock_api_get_forecast(forecast_json):
    """Patch the API client so it returns a parsed fixture forecast."""
    client_for_parsing = GooglePollenApiClient("dummy", None)
    parsed = client_for_parsing._parse_forecast(forecast_json)

    with patch.object(
        GooglePollenApiClient,
        "async_get_forecast",
        new=AsyncMock(return_value=parsed),
    ) as mock:
        yield mock
