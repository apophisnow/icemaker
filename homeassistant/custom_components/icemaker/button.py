"""Button platform for Icemaker integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Coroutine, Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IcemakerApiClient, IcemakerCoordinator


@dataclass(frozen=True, kw_only=True)
class IcemakerButtonEntityDescription(ButtonEntityDescription):
    """Describes an Icemaker button entity."""

    press_fn: Callable[[IcemakerApiClient], Coroutine[Any, Any, bool]]


BUTTON_DESCRIPTIONS: tuple[IcemakerButtonEntityDescription, ...] = (
    IcemakerButtonEntityDescription(
        key="emergency_stop",
        translation_key="emergency_stop",
        name="Emergency Stop",
        icon="mdi:alert-octagon",
        press_fn=lambda client: client.emergency_stop(),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Icemaker buttons based on a config entry."""
    coordinator: IcemakerCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        IcemakerButton(coordinator, description, entry)
        for description in BUTTON_DESCRIPTIONS
    )


class IcemakerButton(CoordinatorEntity[IcemakerCoordinator], ButtonEntity):
    """Representation of an Icemaker control button."""

    entity_description: IcemakerButtonEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: IcemakerCoordinator,
        description: IcemakerButtonEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Icemaker",
            "manufacturer": "Custom",
            "model": "Icemaker Controller",
        }

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.entity_description.press_fn(self.coordinator.client)
        await self.coordinator.async_request_refresh()
