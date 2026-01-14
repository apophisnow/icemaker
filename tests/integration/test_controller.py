"""Integration tests for the icemaker controller."""

import asyncio

import pytest

from icemaker.config import IcemakerConfig, StateConfig
from icemaker.core.controller import IcemakerController
from icemaker.core.states import IcemakerState
from icemaker.hal.base import RelayName
from icemaker.simulator.simulated_hal import create_simulated_hal
from icemaker.simulator.thermal_model import ThermalParameters


@pytest.fixture
def fast_config() -> IcemakerConfig:
    """Configuration with very short timeouts for testing."""
    config = IcemakerConfig()
    config.prechill = StateConfig(target_temp=50.0, timeout_seconds=5)
    config.ice_making = StateConfig(target_temp=30.0, timeout_seconds=10)
    config.harvest = StateConfig(target_temp=60.0, timeout_seconds=5)
    config.rechill = StateConfig(target_temp=45.0, timeout_seconds=5)
    config.bin_full_threshold = 35.0
    config.poll_interval = 0.1
    config.use_simulator = True
    return config


@pytest.fixture
def fast_thermal_params() -> ThermalParameters:
    """Fast thermal parameters for testing."""
    return ThermalParameters(
        compressor_cooling_rate=5.0,  # Very fast
        hot_gas_heating_rate=20.0,  # Very fast
        natural_warming_rate=1.0,
        speed_multiplier=10.0,
    )


class TestControllerInitialization:
    """Test controller initialization."""

    @pytest.mark.asyncio
    async def test_controller_initializes(self, fast_config: IcemakerConfig) -> None:
        """Controller should initialize successfully."""
        gpio, sensors, model = create_simulated_hal()
        controller = IcemakerController(
            config=fast_config,
            gpio=gpio,
            sensors=sensors,
            thermal_model=model,
        )

        await controller.initialize()
        assert controller.fsm.state == IcemakerState.IDLE

    @pytest.mark.asyncio
    async def test_controller_starts_in_idle(
        self, fast_config: IcemakerConfig
    ) -> None:
        """Controller should start in IDLE state."""
        gpio, sensors, model = create_simulated_hal()
        controller = IcemakerController(
            config=fast_config,
            gpio=gpio,
            sensors=sensors,
            thermal_model=model,
        )

        await controller.initialize()
        assert controller.fsm.state == IcemakerState.IDLE
        await controller.stop()


class TestControllerCycleControl:
    """Test cycle start/stop functionality."""

    @pytest.mark.asyncio
    async def test_start_cycle_from_idle(
        self, fast_config: IcemakerConfig
    ) -> None:
        """Should be able to start cycle from IDLE."""
        gpio, sensors, model = create_simulated_hal()
        controller = IcemakerController(
            config=fast_config,
            gpio=gpio,
            sensors=sensors,
            thermal_model=model,
        )

        await controller.initialize()
        success = await controller.start_cycle()

        assert success
        assert controller.fsm.state == IcemakerState.CHILL
        await controller.stop()

    @pytest.mark.asyncio
    async def test_start_cycle_fails_when_not_idle(
        self, fast_config: IcemakerConfig
    ) -> None:
        """Should not be able to start cycle when not in IDLE."""
        gpio, sensors, model = create_simulated_hal()
        controller = IcemakerController(
            config=fast_config,
            gpio=gpio,
            sensors=sensors,
            thermal_model=model,
        )

        await controller.initialize()
        await controller.start_cycle()  # Now in CHILL

        # Try to start again
        success = await controller.start_cycle()
        assert not success
        await controller.stop()

    @pytest.mark.asyncio
    async def test_emergency_stop(self, fast_config: IcemakerConfig) -> None:
        """Emergency stop should turn off all relays and go to IDLE."""
        gpio, sensors, model = create_simulated_hal()
        controller = IcemakerController(
            config=fast_config,
            gpio=gpio,
            sensors=sensors,
            thermal_model=model,
        )

        await controller.initialize()
        await controller.start_cycle()

        # Turn on some relays
        await gpio.set_relay(RelayName.COMPRESSOR_1, True)
        await gpio.set_relay(RelayName.CONDENSER_FAN, True)

        await controller.emergency_stop()

        assert controller.fsm.state == IcemakerState.IDLE

        # All relays should be off
        states = await gpio.get_all_relays()
        for state in states.values():
            assert state is False

        await controller.stop()


class TestChillState:
    """Test CHILL state behavior."""

    @pytest.mark.asyncio
    async def test_chill_activates_cooling(
        self, fast_config: IcemakerConfig
    ) -> None:
        """CHILL should activate compressor and condenser."""
        gpio, sensors, model = create_simulated_hal()
        controller = IcemakerController(
            config=fast_config,
            gpio=gpio,
            sensors=sensors,
            thermal_model=model,
        )

        await controller.initialize()
        await controller.start_cycle()

        # Run one iteration of CHILL handler
        await controller._handle_chill(controller.fsm, controller.fsm.context)

        states = await gpio.get_all_relays()
        assert states[RelayName.COMPRESSOR_1] is True
        assert states[RelayName.COMPRESSOR_2] is True
        assert states[RelayName.CONDENSER_FAN] is True

        await controller.stop()


class TestHeatState:
    """Test HEAT state behavior."""

    @pytest.mark.asyncio
    async def test_heat_activates_heating(
        self, fast_config: IcemakerConfig
    ) -> None:
        """HEAT should activate hot gas solenoid and water valve."""
        gpio, sensors, model = create_simulated_hal()
        controller = IcemakerController(
            config=fast_config,
            gpio=gpio,
            sensors=sensors,
            thermal_model=model,
        )

        await controller.initialize()

        # Set plate temp below harvest target so heating activates
        controller.fsm.context.plate_temp = 10.0  # Below 60°F harvest target

        # Manually transition to HEAT state for testing
        await controller.fsm.transition_to(IcemakerState.CHILL)
        await controller.fsm.transition_to(IcemakerState.ICE)
        await controller.fsm.transition_to(IcemakerState.HEAT)

        # Run HEAT handler
        await controller._handle_heat(controller.fsm, controller.fsm.context)

        states = await gpio.get_all_relays()
        assert states[RelayName.HOT_GAS_SOLENOID] is True
        assert states[RelayName.WATER_VALVE] is True
        assert states[RelayName.CONDENSER_FAN] is False

        await controller.stop()


class TestSimulatedCycle:
    """Test full cycle with simulated thermal model."""

    @pytest.mark.asyncio
    async def test_chill_reaches_target(
        self,
        fast_config: IcemakerConfig,
        fast_thermal_params: ThermalParameters,
    ) -> None:
        """CHILL should transition to ICE when target is reached."""
        gpio, sensors, model = create_simulated_hal(fast_thermal_params)
        controller = IcemakerController(
            config=fast_config,
            gpio=gpio,
            sensors=sensors,
            thermal_model=model,
        )

        await controller.initialize()
        await model.start(update_interval=0.01)

        # Start cycle (CHILL)
        await controller.start_cycle()
        assert controller.fsm.state == IcemakerState.CHILL

        # Simulate reaching target temperature directly
        controller.fsm.context.plate_temp = 40.0  # Below 50°F prechill target

        # Run handler which should detect target reached
        next_state = await controller._handle_chill(
            controller.fsm, controller.fsm.context
        )

        # Should indicate transition to ICE
        assert next_state == IcemakerState.ICE

        await model.stop()
        await controller.stop()
