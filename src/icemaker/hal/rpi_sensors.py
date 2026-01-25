"""Real temperature sensor implementation for Raspberry Pi."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from .base import SensorName, TemperatureSensorInterface

if TYPE_CHECKING:
    from w1thermsensor import W1ThermSensor

logger = logging.getLogger(__name__)


class RaspberryPiSensors(TemperatureSensorInterface):
    """Real temperature sensor implementation using W1ThermSensor.

    Interfaces with DS18B20 1-Wire temperature sensors connected
    to the Raspberry Pi.
    """

    def __init__(self) -> None:
        self._sensors: dict[SensorName, Any] = {}

    async def setup(self, sensor_ids: dict[SensorName, str]) -> None:
        """Initialize temperature sensors.

        Args:
            sensor_ids: Mapping of sensor names to their hardware IDs.
        """
        from w1thermsensor import W1ThermSensor

        for name, sensor_id in sensor_ids.items():
            self._sensors[name] = W1ThermSensor(sensor_id=sensor_id)
            logger.debug(
                "Initialized sensor %s with ID %s",
                name.value,
                sensor_id,
            )

        logger.info("RaspberryPiSensors initialized with %d sensors", len(sensor_ids))

    async def read_temperature(self, sensor: SensorName) -> float:
        """Read temperature from a sensor.

        Runs the blocking I/O operation in an executor to avoid
        blocking the event loop.

        Args:
            sensor: The sensor to read.

        Returns:
            Temperature in degrees Fahrenheit.

        Raises:
            ValueError: If sensor was not configured during setup.
        """
        from w1thermsensor import Unit

        sensor_obj = self._sensors.get(sensor)
        if sensor_obj is None:
            raise ValueError(f"Unknown sensor: {sensor}")

        # Run blocking I/O in executor
        loop = asyncio.get_event_loop()
        temp = await loop.run_in_executor(
            None,
            lambda: sensor_obj.get_temperature(Unit.DEGREES_F),
        )
        return float(temp)

    async def read_all_temperatures(self) -> dict[SensorName, float]:
        """Read all sensor temperatures.

        Returns:
            Mapping of sensor names to temperatures in Fahrenheit.
        """
        results: dict[SensorName, float] = {}
        for name in self._sensors:
            results[name] = await self.read_temperature(name)
        return results
