"""Tests for Google Pollen diagnostics."""

from __future__ import annotations

from homeassistant.components.diagnostics import REDACTED
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.google_pollen.const import CONF_API_KEY, DOMAIN
from custom_components.google_pollen.diagnostics import (
    async_get_config_entry_diagnostics,
)

USER_INPUT = {
    CONF_API_KEY: "test-key",
    CONF_LATITUDE: 37.7749,
    CONF_LONGITUDE: -122.4194,
}


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Google Pollen",
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_diagnostics_redacts_sensitive_fields(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """API key and coordinates are redacted from the entry data."""
    entry = await _setup(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    entry_data = diagnostics["entry"]["data"]
    assert entry_data[CONF_API_KEY] == REDACTED
    assert entry_data[CONF_LATITUDE] == REDACTED
    assert entry_data[CONF_LONGITUDE] == REDACTED


async def test_diagnostics_payload_shape(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """Coordinator state and the serialized forecast are included."""
    entry = await _setup(hass)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    coordinator = diagnostics["coordinator"]
    assert coordinator["last_update_success"] is True
    assert coordinator["update_interval_seconds"] == 6 * 3600
    assert "GRASS" in coordinator["attributes_by_type"]

    forecast = diagnostics["forecast"]
    assert forecast["region_code"] == "US"
    assert forecast["daily_info"]
