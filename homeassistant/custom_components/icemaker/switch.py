"""Switch platform for Icemaker integration."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import IcemakerCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Icemaker switches based on a config entry."""
    coordinator: IcemakerCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities([
        IcemakerCycleSwitch(coordinator, entry),
        IcemakerPrimingSwitch(coordinator, entry),
    ])


class IcemakerCycleSwitch(CoordinatorEntity[IcemakerCoordinator], SwitchEntity):
    """Switch to control ice-making cycle."""

    _attr_has_entity_name = True
    _attr_name = "Cycle"
    _attr_icon = "mdi:snowflake"

    def __init__(
        self,
        coordinator: IcemakerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_cycle"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Icemaker",
            "manufacturer": "Custom",
            "model": "Icemaker Controller",
        }

    @property
    def is_on(self) -> bool:
        """Return true if cycle is running."""
        state = self.coordinator.data.state
        # Cycle is "on" when actively making ice (POWER_ON, CHILL, ICE, HEAT)
        return state in ("POWER_ON", "CHILL", "ICE", "HEAT")

    async def async_turn_on(self, **kwargs) -> None:
        """Start the ice-making cycle."""
        await self.coordinator.client.start_icemaking()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Stop the ice-making cycle."""
        await self.coordinator.client.stop_icemaking()
        await self.coordinator.async_request_refresh()


class IcemakerPrimingSwitch(CoordinatorEntity[IcemakerCoordinator], SwitchEntity):
    """Switch to enable/disable priming on startup."""

    _attr_has_entity_name = True
    _attr_name = "Priming Enabled"
    _attr_icon = "mdi:water-pump"

    def __init__(
        self,
        coordinator: IcemakerCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_priming_enabled"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Icemaker",
            "manufacturer": "Custom",
            "model": "Icemaker Controller",
        }

    @property
    def is_on(self) -> bool:
        """Return true if priming is enabled."""
        if self.coordinator.data.config is None:
            return False
        return self.coordinator.data.config.priming_enabled

    async def async_turn_on(self, **kwargs) -> None:
        """Enable priming."""
        await self.coordinator.client.update_config(priming_enabled=True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Disable priming."""
        await self.coordinator.client.update_config(priming_enabled=False)
        await self.coordinator.async_request_refresh()
