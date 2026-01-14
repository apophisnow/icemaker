"""Mock temperature sensor implementation for testing."""

import logging
from typing import Callable, Optional

from .base import SensorName, TemperatureSensorInterface

logger = logging.getLogger(__name__)

# Type for dynamic temperature provider function
TemperatureProvider = Callable[[SensorName], float]


class MockSensors(TemperatureSensorInterface):
    """Mock temperature sensors for testing.

    Supports both static temperature values (set manually) and
    dynamic temperature providers (for simulator integration).
    """

    def __init__(
        self,
        initial_temps: Optional[dict[SensorName, float]] = None,
    ) -> None:
        """Initialize mock sensors.

        Args:
            initial_temps: Initial temperature values. Defaults to 70°F
                for all sensors if not provided.
        """
        self._temps: dict[SensorName, float] = initial_temps or {
            SensorName.PLATE: 70.0,
            SensorName.ICE_BIN: 70.0,
        }
        self._temp_provider: Optional[TemperatureProvider] = None

    def set_temperature(self, sensor: SensorName, temp: float) -> None:
        """Manually set temperature for a sensor.

        Useful for testing specific temperature scenarios.

        Args:
            sensor: The sensor to set.
            temp: Temperature in Fahrenheit.
        """
        self._temps[sensor] = temp

    def set_temperature_provider(self, provider: TemperatureProvider) -> None:
        """Set dynamic temperature provider.

        When set, temperatures are read from the provider function
        instead of static values. Used for simulator integration.

        Args:
            provider: Function that takes SensorName and returns temperature.
        """
        self._temp_provider = provider

    async def setup(self, sensor_ids: dict[SensorName, str]) -> None:
        """Initialize mock temperature sensors.

        Args:
            sensor_ids: Mapping of sensor names to their hardware IDs
                (ignored in mock, but matches interface).
        """
        logger.info("[MOCK] Temperature sensors initialized")

    async def read_temperature(self, sensor: SensorName) -> float:
        """Read temperature from a sensor.

        Args:
            sensor: The sensor to read.

        Returns:
            Temperature in degrees Fahrenheit.
        """
        if self._temp_provider:
            return self._temp_provider(sensor)
        return self._temps.get(sensor, 70.0)

    async def read_all_temperatures(self) -> dict[SensorName, float]:
        """Read all sensor temperatures.

        Returns:
            Mapping of sensor names to temperatures in Fahrenheit.
        """
        if self._temp_provider:
            return {s: self._temp_provider(s) for s in SensorName}
        return dict(self._temps)
