"""Constants for the Google Pollen integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "google_pollen"

# Configuration
CONF_API_KEY: Final = "api_key"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"

# API
API_BASE_URL: Final = "https://pollen.googleapis.com/v1/forecast:lookup"
DEFAULT_FORECAST_DAYS: Final = 5

# Update interval
DEFAULT_UPDATE_INTERVAL: Final = timedelta(hours=6)

# Pollen types
POLLEN_TYPE_GRASS: Final = "GRASS"
POLLEN_TYPE_TREE: Final = "TREE"
POLLEN_TYPE_WEED: Final = "WEED"

POLLEN_TYPES: Final = [
    POLLEN_TYPE_GRASS,
    POLLEN_TYPE_TREE,
    POLLEN_TYPE_WEED,
]

# UPI Categories
UPI_CATEGORY_NONE: Final = "None"
UPI_CATEGORY_VERY_LOW: Final = "Very Low"
UPI_CATEGORY_LOW: Final = "Low"
UPI_CATEGORY_MODERATE: Final = "Moderate"
UPI_CATEGORY_HIGH: Final = "High"
UPI_CATEGORY_VERY_HIGH: Final = "Very High"

# Sensor types
SENSOR_TYPE_INDEX: Final = "index"
SENSOR_TYPE_CATEGORY: Final = "category"
SENSOR_TYPE_IN_SEASON: Final = "in_season"

# Attribution
ATTRIBUTION: Final = "Data provided by Google Pollen API"
