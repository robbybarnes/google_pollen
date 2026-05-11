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
