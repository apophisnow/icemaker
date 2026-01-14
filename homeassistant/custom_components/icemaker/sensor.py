"""Sensor platform for Icemaker integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IcemakerCoordinator, IcemakerData


@dataclass(frozen=True, kw_only=True)
class IcemakerSensorEntityDescription(SensorEntityDescription):
    """Describes an Icemaker sensor entity."""

    value_fn: Callable[[IcemakerData], Any]


SENSOR_DESCRIPTIONS: tuple[IcemakerSensorEntityDescription, ...] = (
    IcemakerSensorEntityDescription(
        key="state",
        translation_key="state",
        name="State",
        icon="mdi:state-machine",
        value_fn=lambda data: data.state,
    ),
    IcemakerSensorEntityDescription(
        key="plate_temperature",
        translation_key="plate_temperature",
        name="Plate Temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.plate_temp,
    ),
    IcemakerSensorEntityDescription(
        key="bin_temperature",
        translation_key="bin_temperature",
        name="Bin Temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.bin_temp,
    ),
    IcemakerSensorEntityDescription(
        key="target_temperature",
        translation_key="target_temperature",
        name="Target Temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=SensorDeviceClass.TEMPERATURE,
        suggested_display_precision=1,
        value_fn=lambda data: data.target_temp,
    ),
    IcemakerSensorEntityDescription(
        key="cycle_count",
        translation_key="cycle_count",
        name="Cycle Count",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: data.cycle_count,
    ),
    IcemakerSensorEntityDescription(
        key="time_in_state",
        translation_key="time_in_state",
        name="Time in State",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        suggested_display_precision=0,
        value_fn=lambda data: data.time_in_state_seconds,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Icemaker sensors based on a config entry."""
    coordinator: IcemakerCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        IcemakerSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class IcemakerSensor(CoordinatorEntity[IcemakerCoordinator], SensorEntity):
    """Representation of an Icemaker sensor."""

    entity_description: IcemakerSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IcemakerCoordinator,
        description: IcemakerSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Icemaker",
            "manufacturer": "Custom",
            "model": "Icemaker Controller",
        }

    @property
    def native_value(self) -> Any:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional state attributes."""
        if self.entity_description.key == "state":
            data = self.coordinator.data
            return {
                "previous_state": data.previous_state,
                "chill_mode": data.chill_mode,
            }
        return None
