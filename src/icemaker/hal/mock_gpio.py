"""Mock GPIO implementation for testing and non-Pi development."""

from __future__ import annotations

import logging
from typing import Optional

from .base import GPIOInterface, RelayChangeCallback, RelayConfig, RelayName

logger = logging.getLogger(__name__)


class MockGPIO(GPIOInterface):
    """Mock GPIO for testing and non-Pi development.

    Tracks relay states in memory and supports callbacks for
    integration with the thermal simulator.
    """

    def __init__(self) -> None:
        self._states: dict[RelayName, bool] = {}
        self._configs: dict[RelayName, RelayConfig] = {}
        self._on_change: Optional[RelayChangeCallback] = None

    def set_change_callback(self, callback: RelayChangeCallback) -> None:
        """Set callback for relay state changes.

        Used for simulator integration where relay changes affect
        temperature simulation.

        Args:
            callback: Function called with (relay, new_state) on changes.
        """
        self._on_change = callback

    async def setup(self, relay_configs: dict[RelayName, RelayConfig]) -> None:
        """Initialize mock GPIO pins.

        Args:
            relay_configs: Mapping of relay names to their configurations.
        """
        self._configs = relay_configs
        for relay in relay_configs:
            self._states[relay] = False
        logger.info("MockGPIO initialized with %d relays", len(relay_configs))

    async def set_relay(self, relay: RelayName, on: bool) -> None:
        """Set relay state.

        Args:
            relay: The relay to control.
            on: True to turn relay ON, False to turn OFF.

        Raises:
            ValueError: If relay was not configured during setup.
        """
        if relay not in self._configs:
            raise ValueError(f"Unknown relay: {relay}")

        old_state = self._states.get(relay, False)
        self._states[relay] = on

        if self._on_change and old_state != on:
            self._on_change(relay, on)

        logger.debug("[MOCK] Relay %s: %s", relay.value, "ON" if on else "OFF")

    async def get_relay(self, relay: RelayName) -> bool:
        """Get current relay state.

        Args:
            relay: The relay to query.

        Returns:
            True if relay is ON, False if OFF.
        """
        return self._states.get(relay, False)

    async def get_all_relays(self) -> dict[RelayName, bool]:
        """Get all relay states.

        Returns:
            Mapping of relay names to their current states.
        """
        return dict(self._states)

    async def cleanup(self) -> None:
        """Clean up mock GPIO resources."""
        for relay in self._states:
            if self._states[relay]:
                await self.set_relay(relay, False)
        logger.info("[MOCK] GPIO cleanup complete")
