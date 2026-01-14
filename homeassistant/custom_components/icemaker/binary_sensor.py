"""Binary sensor platform for Icemaker integration."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, RELAY_FRIENDLY_NAMES, RELAY_NAMES
from .coordinator import IcemakerCoordinator


@dataclass(frozen=True, kw_only=True)
class IcemakerBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes an Icemaker binary sensor entity."""

    relay_key: str


def _create_relay_descriptions() -> tuple[IcemakerBinarySensorEntityDescription, ...]:
    """Create binary sensor descriptions for all relays."""
    descriptions = []
    for relay in RELAY_NAMES:
        descriptions.append(
            IcemakerBinarySensorEntityDescription(
                key=relay.lower(),
                translation_key=relay.lower(),
                device_class=BinarySensorDeviceClass.RUNNING,
                relay_key=relay,
            )
        )
    return tuple(descriptions)


BINARY_SENSOR_DESCRIPTIONS = _create_relay_descriptions()


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Icemaker binary sensors based on a config entry."""
    coordinator: IcemakerCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        IcemakerRelaySensor(coordinator, description, entry)
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class IcemakerRelaySensor(CoordinatorEntity[IcemakerCoordinator], BinarySensorEntity):
    """Representation of an Icemaker relay as a binary sensor."""

    entity_description: IcemakerBinarySensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IcemakerCoordinator,
        description: IcemakerBinarySensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_relay_{description.key}"
        self._attr_name = RELAY_FRIENDLY_NAMES.get(
            description.relay_key, description.relay_key
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Icemaker",
            "manufacturer": "Custom",
            "model": "Icemaker Controller",
        }

    @property
    def is_on(self) -> bool | None:
        """Return true if the relay is on."""
        relays = self.coordinator.data.relays
        return relays.get(self.entity_description.relay_key, False)
