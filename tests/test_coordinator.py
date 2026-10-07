"""Tests for the Google Pollen coordinator."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.google_pollen.api import (
    GooglePollenApiAuthError,
    GooglePollenApiClient,
    GooglePollenApiConnectionError,
)
from custom_components.google_pollen.const import CONF_API_KEY, DOMAIN
from custom_components.google_pollen.coordinator import (
    GooglePollenDataUpdateCoordinator,
)

USER_INPUT = {
    CONF_API_KEY: "test-key",
    CONF_LATITUDE: 37.7749,
    CONF_LONGITUDE: -122.4194,
}


def _make_coordinator(hass: HomeAssistant) -> GooglePollenDataUpdateCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)
    client = GooglePollenApiClient("dummy", session=None)
    return GooglePollenDataUpdateCoordinator(
        hass,
        config_entry=entry,
        client=client,
        latitude=USER_INPUT[CONF_LATITUDE],
        longitude=USER_INPUT[CONF_LONGITUDE],
    )


async def test_auth_error_raises_config_entry_auth_failed(
    hass: HomeAssistant,
) -> None:
    """An API auth error must trigger reauth, not just an UpdateFailed."""
    coordinator = _make_coordinator(hass)
    coordinator.client.async_get_forecast = AsyncMock(
        side_effect=GooglePollenApiAuthError("bad key")
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_connection_error_raises_update_failed(hass: HomeAssistant) -> None:
    """Network errors continue to surface as UpdateFailed."""
    coordinator = _make_coordinator(hass)
    coordinator.client.async_get_forecast = AsyncMock(
        side_effect=GooglePollenApiConnectionError("dns")
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_successful_update_builds_attributes_cache(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """A successful refresh populates attributes_by_type from the forecast."""
    coordinator = _make_coordinator(hass)
    await coordinator._async_update_data()

    assert "GRASS" in coordinator.attributes_by_type
    grass_attrs = coordinator.attributes_by_type["GRASS"]
    assert grass_attrs["in_season"] is True
    assert grass_attrs["color"] == "#FFCC00"
    assert any(p["code"] == "GRAMINALES" for p in grass_attrs["in_season_plants"])


async def test_failed_refresh_preserves_last_successful_timestamp(
    hass, mock_api_get_forecast, freezer
):
    """A failed poll cannot advance freshness or replace cached attributes."""
    coordinator = _make_coordinator(hass)
    await coordinator._async_update_data()
    timestamp = coordinator.last_successful_update
    attributes = coordinator.attributes_by_type
    freezer.move_to("2026-04-19T13:00:00+00:00")
    mock_api_get_forecast.side_effect = GooglePollenApiConnectionError(
        "connection failed"
    )
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.last_successful_update == timestamp
    assert coordinator.attributes_by_type is attributes


async def test_old_response_is_not_a_successful_refresh(
    hass, mock_api_get_forecast, freezer
):
    """A valid but expired API forecast must not advance freshness."""
    coordinator = _make_coordinator(hass)
    freezer.move_to("2026-04-21T12:00:00+00:00")
    with pytest.raises(UpdateFailed, match="current UTC date"):
        await coordinator._async_update_data()
    assert coordinator.last_successful_update is None
