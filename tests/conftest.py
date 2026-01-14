"""Pytest fixtures for icemaker tests."""

import pytest

from icemaker.config import IcemakerConfig, StateConfig
from icemaker.core.fsm import AsyncFSM
from icemaker.core.states import IcemakerState
from icemaker.hal.base import DEFAULT_RELAY_CONFIG, DEFAULT_SENSOR_IDS
from icemaker.hal.mock_gpio import MockGPIO
from icemaker.hal.mock_sensors import MockSensors
from icemaker.simulator.thermal_model import ThermalModel, ThermalParameters


@pytest.fixture
def mock_gpio() -> MockGPIO:
    """Create mock GPIO interface."""
    return MockGPIO()


@pytest.fixture
def mock_sensors() -> MockSensors:
    """Create mock temperature sensors."""
    return MockSensors()


@pytest.fixture
async def initialized_gpio(mock_gpio: MockGPIO) -> MockGPIO:
    """GPIO interface initialized with default config."""
    await mock_gpio.setup(DEFAULT_RELAY_CONFIG)
    yield mock_gpio
    await mock_gpio.cleanup()


@pytest.fixture
async def initialized_sensors(mock_sensors: MockSensors) -> MockSensors:
    """Temperature sensors initialized."""
    await mock_sensors.setup(DEFAULT_SENSOR_IDS)
    return mock_sensors


@pytest.fixture
def thermal_model() -> ThermalModel:
    """Create thermal model with default parameters."""
    return ThermalModel()


@pytest.fixture
def fast_thermal_model() -> ThermalModel:
    """Thermal model with accelerated rates for testing."""
    params = ThermalParameters(
        compressor_cooling_rate=1.5,  # 10x faster
        hot_gas_heating_rate=8.0,  # 10x faster
        natural_warming_rate=0.2,  # 10x faster
    )
    return ThermalModel(params)


@pytest.fixture
def fsm() -> AsyncFSM:
    """Create FSM in IDLE state."""
    return AsyncFSM(initial_state=IcemakerState.IDLE, poll_interval=0.1)


@pytest.fixture
def test_config() -> IcemakerConfig:
    """Test configuration with short timeouts."""
    config = IcemakerConfig()
    config.prechill = StateConfig(target_temp=32.0, timeout_seconds=10)
    config.ice_making = StateConfig(target_temp=-2.0, timeout_seconds=30)
    config.harvest = StateConfig(target_temp=38.0, timeout_seconds=10)
    config.rechill = StateConfig(target_temp=35.0, timeout_seconds=10)
    config.poll_interval = 0.1
    return config
