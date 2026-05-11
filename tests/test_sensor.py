"""Tests for Google Pollen sensors."""

from __future__ import annotations

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.google_pollen.const import CONF_API_KEY, DOMAIN

USER_INPUT = {
    CONF_API_KEY: "test-key",
    CONF_LATITUDE: 37.7749,
    CONF_LONGITUDE: -122.4194,
}


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=f"{USER_INPUT[CONF_LATITUDE]}_{USER_INPUT[CONF_LONGITUDE]}",
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_sensor_states(hass: HomeAssistant, mock_api_get_forecast) -> None:
    """Index and category sensors reflect the fixture data."""
    await _setup(hass)

    grass_index = hass.states.get("sensor.google_pollen_grass_pollen_index")
    assert grass_index is not None
    assert grass_index.state == "3"
    assert grass_index.attributes["in_season"] is True

    tree_category = hass.states.get("sensor.google_pollen_tree_pollen_level")
    assert tree_category is not None
    assert tree_category.state == "High"


async def test_sensor_out_of_season_fallbacks(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """Out-of-season pollen types return 0 / 'None' instead of Unknown."""
    await _setup(hass)

    weed_index = hass.states.get("sensor.google_pollen_weed_pollen_index")
    assert weed_index is not None
    assert weed_index.state == "0"

    weed_category = hass.states.get("sensor.google_pollen_weed_pollen_level")
    assert weed_category is not None
    assert weed_category.state == "None"


async def test_color_hex_attribute(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """The color attribute is exposed as a #RRGGBB string."""
    await _setup(hass)

    grass_index = hass.states.get("sensor.google_pollen_grass_pollen_index")
    assert grass_index is not None
    assert grass_index.attributes["color"] == "#FFCC00"


async def test_in_season_plants_attribute(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """In-season plants are bucketed under their parent type sensor."""
    await _setup(hass)

    grass_index = hass.states.get("sensor.google_pollen_grass_pollen_index")
    assert grass_index is not None
    plants = grass_index.attributes.get("in_season_plants")
    assert plants is not None
    codes = [p["code"] for p in plants]
    assert codes == ["GRAMINALES"]
    assert plants[0]["family"] == "Poaceae"

    # Out-of-season plant is excluded from the WEED bucket.
    weed_index = hass.states.get("sensor.google_pollen_weed_pollen_index")
    assert weed_index is not None
    assert "in_season_plants" not in weed_index.attributes
