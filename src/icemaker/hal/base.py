"""Abstract interfaces for hardware abstraction layer."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable


class RelayName(Enum):
    """Relay identifiers matching original icemaker code."""

    WATER_VALVE = "water_valve"
    HOT_GAS_SOLENOID = "hot_gas_solenoid"
    RECIRCULATING_PUMP = "recirculating_pump"
    COMPRESSOR_1 = "compressor_1"
    COMPRESSOR_2 = "compressor_2"
    CONDENSER_FAN = "condenser_fan"
    LED = "LED"
    ICE_CUTTER = "ice_cutter"


class SensorName(Enum):
    """Temperature sensor identifiers."""

    PLATE = "plate"
    ICE_BIN = "ice_bin"


@dataclass
class RelayConfig:
    """Configuration for a single relay."""

    gpio_pin: int
    display_name: str
    active_low: bool = True  # 0=ON, 1=OFF as in original code


# Type alias for relay change callback
RelayChangeCallback = Callable[[RelayName, bool], None]


class GPIOInterface(ABC):
    """Abstract interface for GPIO control.

    All methods are async to support both real hardware (which may need
    executor for blocking I/O) and mock implementations.
    """

    @abstractmethod
    async def setup(self, relay_configs: dict[RelayName, RelayConfig]) -> None:
        """Initialize GPIO pins.

        Args:
            relay_configs: Mapping of relay names to their configurations.
        """

    @abstractmethod
    async def set_relay(self, relay: RelayName, on: bool) -> None:
        """Set relay state.

        Args:
            relay: The relay to control.
            on: True to turn relay ON, False to turn OFF.
        """

    @abstractmethod
    async def get_relay(self, relay: RelayName) -> bool:
        """Get current relay state.

        Args:
            relay: The relay to query.

        Returns:
            True if relay is ON, False if OFF.
        """

    @abstractmethod
    async def get_all_relays(self) -> dict[RelayName, bool]:
        """Get all relay states.

        Returns:
            Mapping of relay names to their current states.
        """

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up GPIO resources.

        Should turn off all relays and release GPIO pins.
        """


class TemperatureSensorInterface(ABC):
    """Abstract interface for temperature sensors.

    All methods are async to support both real hardware (which may need
    executor for blocking I/O) and mock implementations.
    """

    @abstractmethod
    async def setup(self, sensor_ids: dict[SensorName, str]) -> None:
        """Initialize temperature sensors.

        Args:
            sensor_ids: Mapping of sensor names to their hardware IDs.
        """

    @abstractmethod
    async def read_temperature(self, sensor: SensorName) -> float:
        """Read temperature from a sensor.

        Args:
            sensor: The sensor to read.

        Returns:
            Temperature in degrees Fahrenheit.
        """

    @abstractmethod
    async def read_all_temperatures(self) -> dict[SensorName, float]:
        """Read all sensor temperatures.

        Returns:
            Mapping of sensor names to temperatures in Fahrenheit.
        """


# Default relay configuration matching original code GPIO pin assignments
DEFAULT_RELAY_CONFIG: dict[RelayName, RelayConfig] = {
    RelayName.WATER_VALVE: RelayConfig(gpio_pin=12, display_name="Water Valve"),
    RelayName.HOT_GAS_SOLENOID: RelayConfig(gpio_pin=5, display_name="Hot Gas Solenoid"),
    RelayName.RECIRCULATING_PUMP: RelayConfig(gpio_pin=6, display_name="Recirculating Pump"),
    RelayName.COMPRESSOR_1: RelayConfig(gpio_pin=24, display_name="Compressor 1"),
    RelayName.COMPRESSOR_2: RelayConfig(gpio_pin=25, display_name="Compressor 2"),
    RelayName.CONDENSER_FAN: RelayConfig(gpio_pin=23, display_name="Condenser Fan"),
    RelayName.LED: RelayConfig(gpio_pin=22, display_name="LED"),
    RelayName.ICE_CUTTER: RelayConfig(gpio_pin=27, display_name="Ice Cutter"),
}

# Default sensor IDs from original code
DEFAULT_SENSOR_IDS: dict[SensorName, str] = {
    SensorName.ICE_BIN: "3c01f0956abd",
    SensorName.PLATE: "092101487373",
}
