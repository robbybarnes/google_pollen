"""The Google Pollen integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GooglePollenApiClient
from .const import CONF_API_KEY
from .coordinator import GooglePollenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

type GooglePollenConfigEntry = ConfigEntry[GooglePollenDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant, entry: GooglePollenConfigEntry
) -> bool:
    """Set up Google Pollen from a config entry."""
    session = async_get_clientsession(hass)
    client = GooglePollenApiClient(entry.data[CONF_API_KEY], session)

    coordinator = GooglePollenDataUpdateCoordinator(
        hass,
        config_entry=entry,
        client=client,
        latitude=entry.data[CONF_LATITUDE],
        longitude=entry.data[CONF_LONGITUDE],
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GooglePollenConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant, entry: GooglePollenConfigEntry
) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
