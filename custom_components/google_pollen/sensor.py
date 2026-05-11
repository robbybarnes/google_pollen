"""Sensor platform for Google Pollen integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GooglePollenConfigEntry
from .api import PollenForecast
from .const import ATTRIBUTION, POLLEN_TYPES
from .coordinator import GooglePollenDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class GooglePollenSensorEntityDescription(SensorEntityDescription):
    """Describes Google Pollen sensor entity."""

    value_fn: Callable[[PollenForecast], Any]
    pollen_type: str | None = None


def get_pollen_index(forecast: PollenForecast, pollen_type: str) -> int | None:
    """Get the pollen index value for a pollen type."""
    if not forecast.daily_info:
        return None
    today = forecast.daily_info[0]
    pollen_info = today.pollen_types.get(pollen_type)
    if pollen_info:
        if pollen_info.index_info and pollen_info.index_info.value is not None:
            return pollen_info.index_info.value
        # Pollen type exists but no index data (out of season) - return 0
        return 0
    return None


def get_pollen_category(forecast: PollenForecast, pollen_type: str) -> str | None:
    """Get the pollen category for a pollen type."""
    if not forecast.daily_info:
        return None
    today = forecast.daily_info[0]
    pollen_info = today.pollen_types.get(pollen_type)
    if pollen_info:
        if pollen_info.index_info and pollen_info.index_info.category:
            return pollen_info.index_info.category
        # Pollen type exists but no index data (out of season) - return "None"
        return "None"
    return None


def create_sensor_descriptions() -> list[GooglePollenSensorEntityDescription]:
    """Create sensor descriptions for all pollen types."""
    descriptions: list[GooglePollenSensorEntityDescription] = []

    for pollen_type in POLLEN_TYPES:
        slug = pollen_type.lower()
        title = pollen_type.title()

        descriptions.append(
            GooglePollenSensorEntityDescription(
                key=f"{slug}_index",
                translation_key=f"{slug}_index",
                name=f"{title} Pollen Index",
                icon="mdi:flower-pollen",
                state_class=SensorStateClass.MEASUREMENT,
                native_unit_of_measurement="UPI",
                value_fn=partial(get_pollen_index, pollen_type=pollen_type),
                pollen_type=pollen_type,
            )
        )

        descriptions.append(
            GooglePollenSensorEntityDescription(
                key=f"{slug}_category",
                translation_key=f"{slug}_category",
                name=f"{title} Pollen Level",
                icon="mdi:flower-pollen-outline",
                value_fn=partial(get_pollen_category, pollen_type=pollen_type),
            )
        )

    return descriptions


SENSOR_DESCRIPTIONS = create_sensor_descriptions()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GooglePollenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Pollen sensors based on a config entry."""
    coordinator = entry.runtime_data

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
        entry: GooglePollenConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        pollen_type = self.entity_description.pollen_type
        if pollen_type is None or self.coordinator.data is None:
            return None
        return self.coordinator.attributes_by_type.get(pollen_type) or None
