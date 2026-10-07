"""Tests for Google Pollen sensors."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
import yaml

from custom_components.google_pollen.api import (
    GooglePollenApiClient,
    GooglePollenApiConnectionError,
)
from custom_components.google_pollen.const import CONF_API_KEY, DOMAIN
from custom_components.google_pollen.coordinator import (
    GooglePollenDataUpdateCoordinator,
)
from custom_components.google_pollen.sensor import (
    SENSOR_DESCRIPTIONS,
    GooglePollenPlantSensor,
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


async def test_color_hex_attribute(hass: HomeAssistant, mock_api_get_forecast) -> None:
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


async def test_forecast_attribute_has_weather_style_datetime(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """Forecast entries carry both `datetime` (weather-card style) and `date`."""
    await _setup(hass)

    grass_index = hass.states.get("sensor.google_pollen_grass_pollen_index")
    assert grass_index is not None
    forecast = grass_index.attributes["forecast"]
    assert forecast[0]["datetime"] == "2026-04-20"
    assert forecast[0]["date"] == "2026-04-20"
    assert forecast[0]["index"] == 2
    assert forecast[0]["category"] == "Low"


async def test_plant_sensors_disabled_by_default(
    hass: HomeAssistant, mock_api_get_forecast
) -> None:
    """Plant sensors are registered but disabled until the user opts in."""
    entry = await _setup(hass)
    registry = er.async_get(hass)

    for plant in ("graminales", "oak", "mugwort"):
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_plant_{plant}"
        )
        assert entity_id is not None
        registry_entry = registry.async_get(entity_id)
        assert registry_entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        # Disabled entities have no state.
        assert hass.states.get(entity_id) is None


async def test_plant_sensor_states(hass: HomeAssistant, mock_api_get_forecast) -> None:
    """Enabled plant sensors expose per-plant index and description data."""
    with patch.object(
        GooglePollenPlantSensor, "_attr_entity_registry_enabled_default", True
    ):
        await _setup(hass)

    grasses = hass.states.get("sensor.google_pollen_grasses_pollen_index")
    assert grasses is not None
    assert grasses.state == "3"
    assert grasses.attributes["in_season"] is True
    assert grasses.attributes["category"] == "Moderate"
    assert grasses.attributes["family"] == "Poaceae"
    assert grasses.attributes["cross_reaction"] == "Pollen of other grasses"

    # In season but no index data from the API remains unknown.
    oak = hass.states.get("sensor.google_pollen_oak_pollen_index")
    assert oak is not None
    assert oak.state == "unknown"
    assert oak.attributes["in_season"] is True

    # Out of season - 0 with in_season False.
    mugwort = hass.states.get("sensor.google_pollen_mugwort_pollen_index")
    assert mugwort is not None
    assert mugwort.state == "0"
    assert mugwort.attributes["in_season"] is False


async def test_cached_forecast_rolls_over_at_utc_midnight(
    hass, mock_api_get_forecast, freezer
):
    """The real midnight timer updates state/attributes without another API call."""

    freezer.move_to("2026-04-19T23:59:59+00:00")
    entry = await _setup(hass)
    timestamp = entry.runtime_data.last_successful_update
    assert mock_api_get_forecast.call_count == 1
    freezer.move_to("2026-04-20T00:00:01+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    grass = hass.states.get("sensor.google_pollen_grass_pollen_index")
    assert grass.state == "2"
    assert grass.attributes["forecast_date"] == "2026-04-20"
    assert "color" not in grass.attributes
    assert "health_recommendations" not in grass.attributes
    assert hass.states.get("sensor.google_pollen_tree_pollen_index").state == "unknown"
    assert entry.runtime_data.last_successful_update == timestamp
    assert mock_api_get_forecast.call_count == 1


async def test_expired_cache_becomes_unknown_at_midnight(
    hass, mock_api_get_forecast, freezer
):
    """Exhausted cache cannot keep displaying yesterday's pollen."""

    freezer.move_to("2026-04-20T23:59:59+00:00")
    await _setup(hass)
    freezer.move_to("2026-04-21T00:00:01+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    grass = hass.states.get("sensor.google_pollen_grass_pollen_index")
    assert grass.state == "unknown"
    assert grass.attributes["forecast_date"] is None
    assert "in_season" not in grass.attributes
    assert mock_api_get_forecast.call_count == 1


async def test_optional_forecast_sensors_and_freshness(hass, mock_api_get_forecast):
    """Enabled forecast sensors expose future values and coverage information."""

    with patch(
        "custom_components.google_pollen.sensor.SENSOR_DESCRIPTIONS",
        [
            replace(description, entity_registry_enabled_default=True)
            for description in SENSOR_DESCRIPTIONS
        ],
    ):
        await _setup(hass)
    tomorrow = hass.states.get("sensor.google_pollen_grass_pollen_tomorrow_index")
    assert tomorrow.state == "2"
    assert tomorrow.attributes["forecast_date"] == "2026-04-20"
    peak = hass.states.get("sensor.google_pollen_grass_pollen_upcoming_peak_index")
    assert peak.state == "2"
    assert peak.attributes["peak_date"] == "2026-04-20"
    assert peak.attributes["forecast_complete"] is True
    tree = hass.states.get("sensor.google_pollen_tree_pollen_upcoming_peak_index")
    assert tree.state == "unknown"
    assert tree.attributes["forecast_complete"] is False
    timestamp = hass.states.get("sensor.google_pollen_last_successful_update")
    assert timestamp.state == "2026-04-19T12:00:00+00:00"


async def test_optional_forecast_sensors_disabled_by_default(
    hass, mock_api_get_forecast
):
    """Forecast sensors register without cluttering existing dashboards."""
    entry = await _setup(hass)
    registry = er.async_get(hass)
    for code in ("grass", "tree", "weed"):
        for kind in ("tomorrow", "peak"):
            entity_id = registry.async_get_entity_id(
                "sensor", DOMAIN, f"{entry.entry_id}_{code}_{kind}_index"
            )
            assert (
                registry.async_get(entity_id).disabled_by
                is er.RegistryEntryDisabler.INTEGRATION
            )
            assert hass.states.get(entity_id) is None


async def test_plant_forecast_includes_unknown_future_days(hass, mock_api_get_forecast):
    """Plant forecasts preserve absent species as unknown, including season info."""
    with patch.object(
        GooglePollenPlantSensor, "_attr_entity_registry_enabled_default", True
    ):
        await _setup(hass)
    oak = hass.states.get("sensor.google_pollen_oak_pollen_index")
    assert oak.attributes["forecast_date"] == "2026-04-19"
    assert oak.attributes["forecast"][0]["date"] == "2026-04-20"
    assert oak.attributes["forecast"][0]["index"] is None
    assert oak.attributes["forecast"][0]["in_season"] is None


async def test_midnight_listener_is_removed_on_unload(
    hass, mock_api_get_forecast, freezer
):
    """Unloaded entries must not retain the midnight timer."""

    freezer.move_to("2026-04-19T23:59:59+00:00")
    handler = MagicMock()
    with patch.object(
        GooglePollenDataUpdateCoordinator, "async_handle_utc_midnight", handler
    ):
        entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.move_to("2026-04-20T00:00:01+00:00")
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()
    handler.assert_not_called()


async def test_refresh_timestamp_stays_available_during_outage(
    hass, mock_api_get_forecast
):
    """Users can still inspect freshness while current pollen is unavailable."""

    entry = await _setup(hass)
    mock_api_get_forecast.side_effect = GooglePollenApiConnectionError("offline")
    await entry.runtime_data.async_refresh()
    await hass.async_block_till_done()
    assert (
        hass.states.get("sensor.google_pollen_grass_pollen_index").state
        == "unavailable"
    )
    assert (
        hass.states.get("sensor.google_pollen_last_successful_update").state
        == "2026-04-19T12:00:00+00:00"
    )


async def test_future_only_plants_are_discovered(
    hass, mock_api_get_forecast, forecast_json
):
    """Species appearing only in tomorrow's forecast get optional entities."""

    forecast_json["dailyInfo"][1]["plantInfo"] = [
        {
            "code": "BIRCH",
            "displayName": "Birch",
            "inSeason": True,
            "indexInfo": {"value": 4},
        }
    ]
    mock_api_get_forecast.return_value = GooglePollenApiClient(
        "dummy", None
    )._parse_forecast(forecast_json)
    with patch.object(
        GooglePollenPlantSensor, "_attr_entity_registry_enabled_default", True
    ):
        entry = await _setup(hass)
    birch = hass.states.get("sensor.google_pollen_birch_pollen_index")
    assert birch.state == "unknown"
    assert birch.attributes["forecast"][0]["index"] == 4
    assert (
        er.async_get(hass).async_get_entity_id(
            "sensor", DOMAIN, f"{entry.entry_id}_plant_birch"
        )
        is not None
    )


async def test_dashboard_templates_render_with_missing_and_available_data(
    hass, mock_api_get_forecast
):
    """The copyable native-card dashboard handles unknown data and forecasts."""

    dashboard = yaml.safe_load(
        (Path(__file__).parents[1] / "examples/pollen-dashboard.yaml").read_text()
    )
    markdown = [
        card["content"] for card in dashboard["cards"] if card["type"] == "markdown"
    ]
    empty = [Template(content, hass).async_render() for content in markdown]
    assert "No upcoming forecast is available" in empty[0]
    assert "Current pollen data is unavailable" in empty[1]
    await _setup(hass)
    rendered = [Template(content, hass).async_render() for content in markdown]
    assert "2026-04-20" in rendered[0]
    assert "2 · Low ↓" in rendered[0]
    assert "Grasses" in rendered[1]
    assert "Close windows" in rendered[1]
