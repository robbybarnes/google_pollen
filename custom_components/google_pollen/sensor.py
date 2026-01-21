"""Sensor platform for Google Pollen integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import PollenForecast, PollenTypeInfo
from .const import ATTRIBUTION, DOMAIN, POLLEN_TYPES
from .coordinator import GooglePollenDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class GooglePollenSensorEntityDescription(SensorEntityDescription):
    """Describes Google Pollen sensor entity."""

    value_fn: Callable[[PollenForecast, str], Any]
    extra_state_attributes_fn: Callable[[PollenForecast, str], dict[str, Any]] | None = None


def get_pollen_index(forecast: PollenForecast, pollen_type: str) -> int | None:
    """Get the pollen index value for a pollen type."""
    if not forecast.daily_info:
        return None
    today = forecast.daily_info[0]
    pollen_info = today.pollen_types.get(pollen_type)
    if pollen_info and pollen_info.index_info:
        return pollen_info.index_info.value
    return None


def get_pollen_category(forecast: PollenForecast, pollen_type: str) -> str | None:
    """Get the pollen category for a pollen type."""
    if not forecast.daily_info:
        return None
    today = forecast.daily_info[0]
    pollen_info = today.pollen_types.get(pollen_type)
    if pollen_info and pollen_info.index_info:
        return pollen_info.index_info.category
    return None


def get_pollen_in_season(forecast: PollenForecast, pollen_type: str) -> bool | None:
    """Get whether a pollen type is in season."""
    if not forecast.daily_info:
        return None
    today = forecast.daily_info[0]
    pollen_info = today.pollen_types.get(pollen_type)
    if pollen_info:
        return pollen_info.in_season
    return None


def get_pollen_attributes(forecast: PollenForecast, pollen_type: str) -> dict[str, Any]:
    """Get extra attributes for a pollen type."""
    attrs: dict[str, Any] = {}
    if not forecast.daily_info:
        return attrs

    today = forecast.daily_info[0]
    pollen_info = today.pollen_types.get(pollen_type)

    if pollen_info:
        attrs["in_season"] = pollen_info.in_season
        if pollen_info.health_recommendations:
            attrs["health_recommendations"] = pollen_info.health_recommendations
        if pollen_info.index_info:
            attrs["index_description"] = pollen_info.index_info.description
            if pollen_info.index_info.color:
                attrs["color"] = pollen_info.index_info.color

    # Add forecast for upcoming days
    forecast_data = []
    for day_info in forecast.daily_info[1:]:  # Skip today
        day_pollen = day_info.pollen_types.get(pollen_type)
        if day_pollen and day_pollen.index_info:
            forecast_data.append({
                "date": day_info.date,
                "index": day_pollen.index_info.value,
                "category": day_pollen.index_info.category,
            })
    if forecast_data:
        attrs["forecast"] = forecast_data

    return attrs


def create_sensor_descriptions() -> list[GooglePollenSensorEntityDescription]:
    """Create sensor descriptions for all pollen types."""
    descriptions = []

    for pollen_type in POLLEN_TYPES:
        pollen_type_lower = pollen_type.lower()
        pollen_type_title = pollen_type.title()

        # Index sensor
        descriptions.append(
            GooglePollenSensorEntityDescription(
                key=f"{pollen_type_lower}_index",
                translation_key=f"{pollen_type_lower}_index",
                name=f"{pollen_type_title} Pollen Index",
                icon="mdi:flower-pollen",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="UPI",
                value_fn=lambda f, pt=pollen_type: get_pollen_index(f, pt),
                extra_state_attributes_fn=lambda f, pt=pollen_type: get_pollen_attributes(f, pt),
            )
        )

        # Category sensor
        descriptions.append(
            GooglePollenSensorEntityDescription(
                key=f"{pollen_type_lower}_category",
                translation_key=f"{pollen_type_lower}_category",
                name=f"{pollen_type_title} Pollen Level",
                icon="mdi:flower-pollen-outline",
                value_fn=lambda f, pt=pollen_type: get_pollen_category(f, pt),
            )
        )

    return descriptions


SENSOR_DESCRIPTIONS = create_sensor_descriptions()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Pollen sensors based on a config entry."""
    coordinator: GooglePollenDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        GooglePollenSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class GooglePollenSensor(
    CoordinatorEntity[GooglePollenDataUpdateCoordinator], SensorEntity
):
    """Representation of a Google Pollen sensor."""

    entity_description: GooglePollenSensorEntityDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: GooglePollenDataUpdateCoordinator,
        description: GooglePollenSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Google Pollen",
            manufacturer="Google",
            model="Pollen API",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url="https://developers.google.com/maps/documentation/pollen",
        )

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data, "")

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        if (
            self.coordinator.data is None
            or self.entity_description.extra_state_attributes_fn is None
        ):
            return None
        return self.entity_description.extra_state_attributes_fn(
            self.coordinator.data, ""
        )
