"""HAL factory with platform auto-detection."""

import logging
from typing import TYPE_CHECKING

from .base import (
    DEFAULT_RELAY_CONFIG,
    DEFAULT_SENSOR_IDS,
    GPIOInterface,
    RelayConfig,
    RelayName,
    SensorName,
    TemperatureSensorInterface,
)

if TYPE_CHECKING:
    from ..simulator.thermal_model import ThermalModel

logger = logging.getLogger(__name__)


def is_raspberry_pi() -> bool:
    """Detect if running on Raspberry Pi.

    Checks /proc/cpuinfo for Raspberry Pi or BCM identifiers.

    Returns:
        True if running on Raspberry Pi, False otherwise.
    """
    try:
        with open("/proc/cpuinfo") as f:
            cpuinfo = f.read()
            return "Raspberry Pi" in cpuinfo or "BCM" in cpuinfo
    except FileNotFoundError:
        return False


def create_hal(
    force_mock: bool = False,
    use_simulator: bool = False,
    relay_configs: dict[RelayName, RelayConfig] | None = None,
    sensor_ids: dict[SensorName, str] | None = None,
) -> tuple[GPIOInterface, TemperatureSensorInterface]:
    """Factory function to create appropriate HAL implementations.

    Automatically detects the platform and creates either real
    Raspberry Pi implementations or mock implementations for
    development/testing.

    Args:
        force_mock: Force mock implementations even on Raspberry Pi.
        use_simulator: Use physics-based simulator (implies mock HAL).
        relay_configs: Custom relay configuration. Uses defaults if None.
        sensor_ids: Custom sensor IDs. Uses defaults if None.

    Returns:
        Tuple of (GPIOInterface, TemperatureSensorInterface).
        When use_simulator=True, returns mocks connected to thermal model.
    """
    configs = relay_configs or DEFAULT_RELAY_CONFIG
    sensors = sensor_ids or DEFAULT_SENSOR_IDS

    if use_simulator:
        from .mock_gpio import MockGPIO
        from .mock_sensors import MockSensors

        logger.info("Using simulated HAL implementations")
        return MockGPIO(), MockSensors()

    if force_mock or not is_raspberry_pi():
        from .mock_gpio import MockGPIO
        from .mock_sensors import MockSensors

        logger.info("Using mock HAL implementations (not on Raspberry Pi)")
        return MockGPIO(), MockSensors()

    from .rpi_gpio import RaspberryPiGPIO
    from .rpi_sensors import RaspberryPiSensors

    logger.info("Using real Raspberry Pi HAL implementations")
    return RaspberryPiGPIO(), RaspberryPiSensors()


def create_hal_with_simulator(
    relay_configs: dict[RelayName, RelayConfig] | None = None,
    sensor_ids: dict[SensorName, str] | None = None,
) -> tuple[GPIOInterface, TemperatureSensorInterface, "ThermalModel"]:
    """Create HAL implementations connected to thermal simulator.

    Creates mock GPIO and sensors that are connected to a physics-based
    thermal model. Relay state changes affect simulated temperatures.

    Args:
        relay_configs: Custom relay configuration. Uses defaults if None.
        sensor_ids: Custom sensor IDs. Uses defaults if None.

    Returns:
        Tuple of (GPIO, Sensors, ThermalModel).
        The thermal model must be started separately with model.run().
    """
    from ..simulator.simulated_hal import create_simulated_hal

    return create_simulated_hal()
