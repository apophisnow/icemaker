"""Hardware abstraction layer for GPIO and sensors."""

from .base import (
    GPIOInterface,
    TemperatureSensorInterface,
    RelayName,
    SensorName,
    RelayConfig,
)
from .factory import create_hal, is_raspberry_pi

__all__ = [
    "GPIOInterface",
    "TemperatureSensorInterface",
    "RelayName",
    "SensorName",
    "RelayConfig",
    "create_hal",
    "is_raspberry_pi",
]
