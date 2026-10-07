"""Regression tests for UTC dates, forecast gaps, and seasonal values."""

from datetime import date

import pytest

from custom_components.google_pollen.api import GooglePollenApiClient
from custom_components.google_pollen.forecast import (
    forecast_day,
    future_forecast,
    index_value,
    upcoming_peak,
)


@pytest.mark.parametrize(
    ("season", "expected"), [(True, None), (False, 0), (None, None)]
)
def test_missing_index_is_zero_only_when_explicitly_out_of_season(
    forecast_json, season, expected
):
    info = forecast_json["dailyInfo"][0]["pollenTypeInfo"][0]
    info.pop("indexInfo")
    info["inSeason"] = season
    forecast = GooglePollenApiClient("dummy", None)._parse_forecast(forecast_json)
    assert index_value(forecast.daily_info[0].pollen_types["GRASS"]) == expected


def test_exact_date_selection_does_not_substitute_nearby_days(forecast_json):
    forecast = GooglePollenApiClient("dummy", None)._parse_forecast(forecast_json)
    assert forecast_day(forecast, date(2026, 4, 20)).date == "2026-04-20"
    assert forecast_day(forecast, date(2026, 4, 21)) is None
    assert forecast_day(forecast, date(2026, 4, 18)) is None


def test_future_forecasts_keep_missing_readings(forecast_json):
    forecast = GooglePollenApiClient("dummy", None)._parse_forecast(forecast_json)
    assert future_forecast(forecast, "TREE")[0]["index"] is None
    assert future_forecast(forecast, "OAK", plant=True)[0]["category"] is None
    assert upcoming_peak(forecast, "TREE") is None
    assert upcoming_peak(forecast, "GRASS")["index"] == 2
