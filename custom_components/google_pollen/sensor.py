"""Sensor platform for Google Pollen integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from functools import partial
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import GooglePollenConfigEntry
from .api import PlantInfo, PollenForecast
from .const import ATTRIBUTION, POLLEN_CATEGORIES, POLLEN_TYPES
from .coordinator import GooglePollenDataUpdateCoordinator
from .forecast import (
    forecast_day,
    future_forecast,
    index_category,
    index_value,
    upcoming_peak,
)

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class GooglePollenSensorEntityDescription(SensorEntityDescription):
    """Describes Google Pollen sensor entity."""

    value_fn: Callable[[PollenForecast], Any]
    pollen_type: str | None = None
    forecast_kind: str | None = None


def get_pollen_index(
    forecast: PollenForecast, pollen_type: str, day_offset: int = 0
) -> int | None:
    """Get a reading for an exact UTC date."""
    target = dt_util.utcnow().date() + timedelta(days=day_offset)
    day = forecast_day(forecast, target)
    return index_value(day.pollen_types.get(pollen_type)) if day else None


def get_pollen_category(forecast: PollenForecast, pollen_type: str) -> str | None:
    """Get the stable category for today's UTC reading."""
    day = forecast_day(forecast)
    return index_category(day.pollen_types.get(pollen_type)) if day else None


def get_peak_index(forecast: PollenForecast, pollen_type: str) -> int | None:
    """Get the largest known index on future returned dates."""
    peak = upcoming_peak(forecast, pollen_type)
    return peak["index"] if peak else None


def create_sensor_descriptions() -> list[GooglePollenSensorEntityDescription]:
    """Create sensor descriptions for all pollen types."""
    descriptions: list[GooglePollenSensorEntityDescription] = []

    for pollen_type in POLLEN_TYPES:
        slug = pollen_type.lower()

        descriptions.append(
            GooglePollenSensorEntityDescription(
                key=f"{slug}_index",
                translation_key=f"{slug}_index",
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
                icon="mdi:flower-pollen-outline",
                device_class=SensorDeviceClass.ENUM,
                options=POLLEN_CATEGORIES,
                value_fn=partial(get_pollen_category, pollen_type=pollen_type),
            )
        )

        descriptions.extend(
            [
                GooglePollenSensorEntityDescription(
                    key=f"{slug}_tomorrow_index",
                    translation_key=f"{slug}_tomorrow_index",
                    icon="mdi:calendar-arrow-right",
                    native_unit_of_measurement="UPI",
                    entity_registry_enabled_default=False,
                    value_fn=partial(
                        get_pollen_index, pollen_type=pollen_type, day_offset=1
                    ),
                    pollen_type=pollen_type,
                    forecast_kind="tomorrow",
                ),
                GooglePollenSensorEntityDescription(
                    key=f"{slug}_peak_index",
                    translation_key=f"{slug}_peak_index",
                    icon="mdi:chart-bell-curve",
                    native_unit_of_measurement="UPI",
                    entity_registry_enabled_default=False,
                    value_fn=partial(get_peak_index, pollen_type=pollen_type),
                    pollen_type=pollen_type,
                    forecast_kind="peak",
                ),
            ]
        )

    descriptions.append(
        GooglePollenSensorEntityDescription(
            key="last_successful_update",
            translation_key="last_successful_update",
            device_class=SensorDeviceClass.TIMESTAMP,
            entity_category=EntityCategory.DIAGNOSTIC,
            value_fn=lambda _: None,
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

    # Per-plant sensors are created from the plants the API reports for
    # this region. New plants can appear mid-season, so keep listening.
    known_plants: set[str] = set()

    def _add_plant_sensors() -> None:
        forecast = coordinator.data
        if forecast is None or not forecast.daily_info:
            return
        new_plants = [
            plant
            for code, plant in sorted(
                {
                    code: plant
                    for day in forecast.daily_info
                    for code, plant in day.plants.items()
                }.items()
            )
            if code not in known_plants
        ]
        if not new_plants:
            return
        known_plants.update(plant.code for plant in new_plants)
        async_add_entities(
            GooglePollenPlantSensor(coordinator, entry, plant) for plant in new_plants
        )

    _add_plant_sensors()
    entry.async_on_unload(coordinator.async_add_listener(_add_plant_sensors))


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
    def available(self) -> bool:
        """Keep the last successful timestamp visible during an API outage."""
        if self.entity_description.key == "last_successful_update":
            return self.coordinator.last_successful_update is not None
        return super().available

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        if self.entity_description.key == "last_successful_update":
            return self.coordinator.last_successful_update
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        attrs = dict(self.coordinator.freshness_attributes)
        pollen_type = self.entity_description.pollen_type
        forecast = self.coordinator.data
        if pollen_type is None or forecast is None:
            return attrs
        kind = self.entity_description.forecast_kind
        if kind is None:
            attrs.update(self.coordinator.attributes_by_type.get(pollen_type, {}))
        else:
            future = future_forecast(forecast, pollen_type)
            attrs["forecast"] = future
            if kind == "tomorrow":
                tomorrow = (dt_util.utcnow().date() + timedelta(days=1)).isoformat()
                attrs["forecast_date"] = tomorrow
                selected = next(
                    (day for day in future if day["date"] == tomorrow), None
                )
                if selected:
                    attrs["category"] = selected["category"]
                    attrs["in_season"] = selected["in_season"]
            else:
                peak = upcoming_peak(forecast, pollen_type)
                attrs["forecast_date"] = peak["date"] if peak else None
                attrs["peak_date"] = peak["date"] if peak else None
                attrs["category"] = peak["category"] if peak else None
                attrs["forecast_complete"] = bool(future) and all(
                    day["index"] is not None for day in future
                )
                attrs["forecast_days"] = len(future)
        return attrs


class GooglePollenPlantSensor(
    CoordinatorEntity[GooglePollenDataUpdateCoordinator], SensorEntity
):
    """Pollen index for a single plant reported by the API.

    Disabled by default; users enable the plants they care about.
    """

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_entity_registry_enabled_default = False
    _attr_icon = "mdi:sprout"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "UPI"

    def __init__(
        self,
        coordinator: GooglePollenDataUpdateCoordinator,
        entry: GooglePollenConfigEntry,
        plant: PlantInfo,
    ) -> None:
        """Initialize the plant sensor."""
        super().__init__(coordinator)
        self._plant_code = plant.code
        display_name = plant.display_name or plant.code.replace("_", " ").title()
        self._attr_name = f"{display_name} Pollen Index"
        self._attr_unique_id = f"{entry.entry_id}_plant_{plant.code.lower()}"
        self._attr_device_info = coordinator.device_info

    def _today_plant(self) -> PlantInfo | None:
        """Return today's data for this plant, if present."""
        forecast = self.coordinator.data
        if forecast is None or not forecast.daily_info:
            return None
        day = forecast_day(forecast)
        return day.plants.get(self._plant_code) if day else None

    @property
    def native_value(self) -> int | None:
        """Return the plant's pollen index."""
        return index_value(self._today_plant())

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        plant = self._today_plant()
        attrs = dict(self.coordinator.freshness_attributes)
        if self.coordinator.data:
            attrs["forecast"] = future_forecast(
                self.coordinator.data, self._plant_code, plant=True
            )
        if plant is None:
            return attrs

        attrs["in_season"] = plant.in_season
        attrs["category"] = index_category(plant)
        if plant.index_info:
            if plant.index_info.category:
                attrs["category"] = plant.index_info.category
            if plant.index_info.description:
                attrs["index_description"] = plant.index_info.description
            if plant.index_info.color:
                attrs["color"] = plant.index_info.color

        if description := plant.plant_description:
            for key, value in (
                ("plant_type", description.plant_type),
                ("family", description.family),
                ("season", description.season),
                ("cross_reaction", description.cross_reaction),
                ("picture", description.picture),
            ):
                if value is not None:
                    attrs[key] = value
        return attrs
