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
        from w1thermsensor.errors import SensorNotReadyError, NoSensorFoundError

        for name, sensor_id in sensor_ids.items():
            try:
                self._sensors[name] = W1ThermSensor(sensor_id=sensor_id)
                logger.info(
                    "Initialized sensor %s with ID %s",
                    name.value,
                    sensor_id,
                )
            except (SensorNotReadyError, NoSensorFoundError) as e:
                logger.error(
                    "Failed to initialize sensor %s (ID: %s): %s",
                    name.value,
                    sensor_id,
                    e,
                )
                # Continue without this sensor - will raise on read
            except Exception as e:
                logger.error(
                    "Unexpected error initializing sensor %s (ID: %s): %s",
                    name.value,
                    sensor_id,
                    e,
                )

        logger.info(
            "RaspberryPiSensors initialized with %d/%d sensors",
            len(self._sensors),
            len(sensor_ids),
        )

    async def read_temperature(self, sensor: SensorName) -> float:
        """Read temperature from a sensor.

        Runs the blocking I/O operation in an executor to avoid
        blocking the event loop.

        Args:
            sensor: The sensor to read.

        Returns:
            Temperature in degrees Fahrenheit, or 70.0 if read fails.

        Raises:
            ValueError: If sensor was not configured during setup.
        """
        from w1thermsensor import Unit
        from w1thermsensor.errors import SensorNotReadyError, NoSensorFoundError

        sensor_obj = self._sensors.get(sensor)
        if sensor_obj is None:
            logger.warning("Sensor %s not initialized, returning default temp", sensor.value)
            return 70.0  # Return room temp as fallback

        try:
            # Run blocking I/O in executor
            loop = asyncio.get_event_loop()
            temp = await loop.run_in_executor(
                None,
                lambda: sensor_obj.get_temperature(Unit.DEGREES_F),
            )
            return float(temp)
        except (SensorNotReadyError, NoSensorFoundError) as e:
            logger.warning("Failed to read sensor %s: %s", sensor.value, e)
            return 70.0  # Return room temp as fallback
        except Exception as e:
            logger.error("Unexpected error reading sensor %s: %s", sensor.value, e)
            return 70.0

    async def read_all_temperatures(self) -> dict[SensorName, float]:
        """Read all sensor temperatures.

        Returns:
            Mapping of sensor names to temperatures in Fahrenheit.
        """
        results: dict[SensorName, float] = {}
        for name in self._sensors:
            results[name] = await self.read_temperature(name)
        return results
