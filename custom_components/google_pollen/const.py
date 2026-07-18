"""Constants for the Google Pollen integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "google_pollen"
DEFAULT_NAME: Final = "Google Pollen"

# Configuration
CONF_API_KEY: Final = "api_key"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_UPDATE_INTERVAL_HOURS: Final = "update_interval_hours"

# API
API_BASE_URL: Final = "https://pollen.googleapis.com/v1/forecast:lookup"
API_TIMEOUT_SECONDS: Final = 30
DEFAULT_FORECAST_DAYS: Final = 5

# Update interval
DEFAULT_UPDATE_INTERVAL_HOURS: Final = 6

# Pollen types
POLLEN_TYPE_GRASS: Final = "GRASS"
POLLEN_TYPE_TREE: Final = "TREE"
POLLEN_TYPE_WEED: Final = "WEED"

POLLEN_TYPES: Final = [
    POLLEN_TYPE_GRASS,
    POLLEN_TYPE_TREE,
    POLLEN_TYPE_WEED,
]

# UPI categories as returned by the API (index 0-5), plus the "None"
# fallback used when a pollen type is out of season.
POLLEN_CATEGORIES: Final = [
    "None",
    "Very Low",
    "Low",
    "Moderate",
    "High",
    "Very High",
]

# Attribution
ATTRIBUTION: Final = "Data provided by Google Pollen API"
