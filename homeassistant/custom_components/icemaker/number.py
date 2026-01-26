"""Number platform for Icemaker integration."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IcemakerApiClient, IcemakerCoordinator, IcemakerData


@dataclass(frozen=True, kw_only=True)
class IcemakerNumberEntityDescription(NumberEntityDescription):
    """Describes an Icemaker number entity."""

    value_fn: Callable[[IcemakerData], float | None]
    api_key: str  # Key to use when updating via API


NUMBER_DESCRIPTIONS: tuple[IcemakerNumberEntityDescription, ...] = (
    # Temperature settings
    IcemakerNumberEntityDescription(
        key="prechill_temp",
        translation_key="prechill_temp",
        name="Prechill Temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=20.0,
        native_max_value=50.0,
        native_step=0.5,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-chevron-down",
        value_fn=lambda data: data.config.prechill_temp if data.config else None,
        api_key="prechill_temp",
    ),
    IcemakerNumberEntityDescription(
        key="ice_target_temp",
        translation_key="ice_target_temp",
        name="Ice Target Temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=-20.0,
        native_max_value=20.0,
        native_step=0.5,
        mode=NumberMode.BOX,
        icon="mdi:snowflake-thermometer",
        value_fn=lambda data: data.config.ice_target_temp if data.config else None,
        api_key="ice_target_temp",
    ),
    IcemakerNumberEntityDescription(
        key="harvest_threshold",
        translation_key="harvest_threshold",
        name="Harvest Threshold",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=30.0,
        native_max_value=60.0,
        native_step=0.5,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-chevron-up",
        value_fn=lambda data: data.config.harvest_threshold if data.config else None,
        api_key="harvest_threshold",
    ),
    IcemakerNumberEntityDescription(
        key="rechill_temp",
        translation_key="rechill_temp",
        name="Rechill Temperature",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=25.0,
        native_max_value=50.0,
        native_step=0.5,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-minus",
        value_fn=lambda data: data.config.rechill_temp if data.config else None,
        api_key="rechill_temp",
    ),
    IcemakerNumberEntityDescription(
        key="bin_full_threshold",
        translation_key="bin_full_threshold",
        name="Bin Full Threshold",
        native_unit_of_measurement=UnitOfTemperature.FAHRENHEIT,
        device_class=NumberDeviceClass.TEMPERATURE,
        native_min_value=20.0,
        native_max_value=50.0,
        native_step=0.5,
        mode=NumberMode.BOX,
        icon="mdi:thermometer-alert",
        value_fn=lambda data: data.config.bin_full_threshold if data.config else None,
        api_key="bin_full_threshold",
    ),
    # Timeout settings
    IcemakerNumberEntityDescription(
        key="prechill_timeout",
        translation_key="prechill_timeout",
        name="Prechill Timeout",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=30,
        native_max_value=600,
        native_step=10,
        mode=NumberMode.BOX,
        icon="mdi:timer-outline",
        value_fn=lambda data: data.config.prechill_timeout if data.config else None,
        api_key="prechill_timeout",
    ),
    IcemakerNumberEntityDescription(
        key="ice_timeout",
        translation_key="ice_timeout",
        name="Ice Timeout",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=300,
        native_max_value=3600,
        native_step=60,
        mode=NumberMode.BOX,
        icon="mdi:timer-sand",
        value_fn=lambda data: data.config.ice_timeout if data.config else None,
        api_key="ice_timeout",
    ),
    IcemakerNumberEntityDescription(
        key="harvest_timeout",
        translation_key="harvest_timeout",
        name="Harvest Timeout",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=60,
        native_max_value=600,
        native_step=10,
        mode=NumberMode.BOX,
        icon="mdi:timer-check-outline",
        value_fn=lambda data: data.config.harvest_timeout if data.config else None,
        api_key="harvest_timeout",
    ),
    IcemakerNumberEntityDescription(
        key="rechill_timeout",
        translation_key="rechill_timeout",
        name="Rechill Timeout",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=60,
        native_max_value=600,
        native_step=10,
        mode=NumberMode.BOX,
        icon="mdi:timer-refresh-outline",
        value_fn=lambda data: data.config.rechill_timeout if data.config else None,
        api_key="rechill_timeout",
    ),
    IcemakerNumberEntityDescription(
        key="harvest_fill_time",
        translation_key="harvest_fill_time",
        name="Harvest Fill Time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=5,
        native_max_value=60,
        native_step=1,
        mode=NumberMode.BOX,
        icon="mdi:water",
        value_fn=lambda data: data.config.harvest_fill_time if data.config else None,
        api_key="harvest_fill_time",
    ),
    IcemakerNumberEntityDescription(
        key="standby_timeout",
        translation_key="standby_timeout",
        name="Standby Timeout",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=60,
        native_max_value=7200,
        native_step=60,
        mode=NumberMode.BOX,
        icon="mdi:timer-pause-outline",
        value_fn=lambda data: data.config.standby_timeout if data.config else None,
        api_key="standby_timeout",
    ),
    # Priming settings
    IcemakerNumberEntityDescription(
        key="priming_flush_time",
        translation_key="priming_flush_time",
        name="Priming Flush Time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=10,
        native_max_value=180,
        native_step=5,
        mode=NumberMode.BOX,
        icon="mdi:water-pump",
        value_fn=lambda data: data.config.priming_flush_time if data.config else None,
        api_key="priming_flush_time",
    ),
    IcemakerNumberEntityDescription(
        key="priming_pump_time",
        translation_key="priming_pump_time",
        name="Priming Pump Time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=5,
        native_max_value=60,
        native_step=5,
        mode=NumberMode.BOX,
        icon="mdi:pump",
        value_fn=lambda data: data.config.priming_pump_time if data.config else None,
        api_key="priming_pump_time",
    ),
    IcemakerNumberEntityDescription(
        key="priming_fill_time",
        translation_key="priming_fill_time",
        name="Priming Fill Time",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=NumberDeviceClass.DURATION,
        native_min_value=5,
        native_max_value=60,
        native_step=5,
        mode=NumberMode.BOX,
        icon="mdi:water-plus",
        value_fn=lambda data: data.config.priming_fill_time if data.config else None,
        api_key="priming_fill_time",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Icemaker number entities based on a config entry."""
    coordinator: IcemakerCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        IcemakerNumber(coordinator, description, entry)
        for description in NUMBER_DESCRIPTIONS
    )


class IcemakerNumber(CoordinatorEntity[IcemakerCoordinator], NumberEntity):
    """Representation of an Icemaker configuration number."""

    entity_description: IcemakerNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IcemakerCoordinator,
        description: IcemakerNumberEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_config_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Icemaker",
            "manufacturer": "Custom",
            "model": "Icemaker Controller",
        }

    @property
    def native_value(self) -> float | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_native_value(self, value: float) -> None:
        """Update the configuration value."""
        api_key = self.entity_description.api_key
        await self.coordinator.client.update_config(**{api_key: value})
        await self.coordinator.async_request_refresh()
