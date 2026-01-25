"""Real GPIO implementation for Raspberry Pi."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from .base import GPIOInterface, RelayConfig, RelayName

if TYPE_CHECKING:
    import RPi.GPIO as GPIO  # noqa: N812

logger = logging.getLogger(__name__)


class RaspberryPiGPIO(GPIOInterface):
    """Real GPIO implementation for Raspberry Pi.

    Uses RPi.GPIO library with active-low relay control
    (0 = ON, 1 = OFF) as in the original icemaker code.
    """

    def __init__(self) -> None:
        self._configs: dict[RelayName, RelayConfig] = {}
        self._states: dict[RelayName, bool] = {}
        self._gpio: Any = None

    async def setup(self, relay_configs: dict[RelayName, RelayConfig]) -> None:
        """Initialize GPIO pins.

        Imports RPi.GPIO and configures all relay pins as outputs
        with initial HIGH state (relay OFF for active-low).

        Args:
            relay_configs: Mapping of relay names to their configurations.
        """
        import RPi.GPIO as GPIO  # noqa: N812

        self._gpio = GPIO
        self._configs = relay_configs

        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        for relay, config in relay_configs.items():
            # Initialize as output, HIGH = OFF for active-low relays
            GPIO.setup(config.gpio_pin, GPIO.OUT, initial=GPIO.HIGH)
            GPIO.output(config.gpio_pin, 1)  # Ensure OFF state
            self._states[relay] = False
            logger.debug(
                "Initialized relay %s on GPIO pin %d",
                relay.value,
                config.gpio_pin,
            )

        logger.info("RaspberryPiGPIO initialized with %d relays", len(relay_configs))

    async def set_relay(self, relay: RelayName, on: bool) -> None:
        """Set relay state.

        Uses active-low control: GPIO LOW (0) = relay ON,
        GPIO HIGH (1) = relay OFF.

        Args:
            relay: The relay to control.
            on: True to turn relay ON, False to turn OFF.

        Raises:
            ValueError: If relay was not configured during setup.
        """
        config = self._configs.get(relay)
        if config is None:
            raise ValueError(f"Unknown relay: {relay}")

        # Active low: 0 = ON, 1 = OFF
        pin_value = 0 if on else 1

        # Run GPIO output in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            self._gpio.output,
            config.gpio_pin,
            pin_value,
        )

        self._states[relay] = on
        logger.debug("Relay %s: %s", relay.value, "ON" if on else "OFF")

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
        """Clean up GPIO resources.

        Turns off all relays and releases GPIO pins.
        """
        if self._gpio is None:
            return

        # Turn off all relays first
        for relay in self._configs:
            if self._states.get(relay, False):
                await self.set_relay(relay, False)

        # Clean up GPIO
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._gpio.cleanup)
        logger.info("RaspberryPiGPIO cleanup complete")
