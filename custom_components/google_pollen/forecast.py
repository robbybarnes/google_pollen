"""Date-aware values shared by pollen and plant sensors."""

from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.util import dt as dt_util

from .api import DailyPollenInfo, PlantInfo, PollenForecast, PollenTypeInfo
from .const import POLLEN_CATEGORIES


def forecast_day(
    forecast: PollenForecast, target: date | None = None
) -> DailyPollenInfo | None:
    """Select an exact UTC date; never substitute yesterday or tomorrow."""
    target_date = (target or dt_util.utcnow().date()).isoformat()
    return next((day for day in forecast.daily_info if day.date == target_date), None)


def index_value(info: PollenTypeInfo | PlantInfo | None) -> int | None:
    """Missing readings are unknown unless explicitly reported out of season."""
    if info is None:
        return None
    if info.index_info is not None:
        return info.index_info.value
    return 0 if info.in_season is False else None


def index_category(info: PollenTypeInfo | PlantInfo | None) -> str | None:
    """Return the stable enum category for a known value."""
    value = index_value(info)
    return POLLEN_CATEGORIES[value] if value is not None else None


def future_forecast(
    forecast: PollenForecast,
    code: str,
    *,
    plant: bool = False,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Include all future returned days, preserving gaps as unknown values."""
    today_str = (today or dt_util.utcnow().date()).isoformat()
    result = []
    for day in forecast.daily_info:
        if day.date <= today_str:
            continue
        info = (day.plants if plant else day.pollen_types).get(code)
        result.append(
            {
                "datetime": day.date,
                "date": day.date,
                "index": index_value(info),
                "category": index_category(info),
                "in_season": info.in_season if info else None,
            }
        )
    return result


def upcoming_peak(forecast: PollenForecast, code: str) -> dict[str, Any] | None:
    """Find the earliest maximum among known future readings."""
    known_days = [
        day for day in future_forecast(forecast, code) if day["index"] is not None
    ]
    return max(known_days, key=lambda day: day["index"]) if known_days else None
