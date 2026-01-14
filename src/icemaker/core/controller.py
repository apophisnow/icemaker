"""Main controller orchestrating FSM, HAL, and state handlers."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from ..config import IcemakerConfig, load_config
from ..hal.base import (
    DEFAULT_RELAY_CONFIG,
    DEFAULT_SENSOR_IDS,
    GPIOInterface,
    RelayName,
    SensorName,
    TemperatureSensorInterface,
)
from ..hal.factory import create_hal, create_hal_with_simulator
from ..simulator.thermal_model import ThermalModel
from .events import Event, EventType, relay_changed_event, temp_reading_event
from .fsm import AsyncFSM, FSMContext
from .states import ChillMode, IcemakerState

logger = logging.getLogger(__name__)


class IcemakerController:
    """Main controller for icemaker operation.

    Orchestrates the FSM, HAL interfaces, and implements state handlers
    that control relay states based on temperature readings.

    The controller implements the ice-making cycle:
    1. POWER_ON: Prime water system
    2. CHILL (prechill): Cool plate to 32°F
    3. ICE: Make ice at -2°F with recirculation
    4. HEAT: Harvest ice at 38°F
    5. CHILL (rechill): Cool to 35°F
    6. Check bin, repeat or idle
    """

    def __init__(
        self,
        config: Optional[IcemakerConfig] = None,
        gpio: Optional[GPIOInterface] = None,
        sensors: Optional[TemperatureSensorInterface] = None,
        thermal_model: Optional[ThermalModel] = None,
    ) -> None:
        """Initialize the controller.

        Args:
            config: Configuration. Loads from files if None.
            gpio: GPIO interface. Auto-created if None.
            sensors: Temperature sensor interface. Auto-created if None.
            thermal_model: Thermal model for simulation. Auto-created if
                config.use_simulator is True and gpio/sensors are None.
        """
        self.config = config or load_config()
        self._gpio = gpio
        self._sensors = sensors
        self._thermal_model = thermal_model
        self._fsm = AsyncFSM(
            initial_state=IcemakerState.IDLE,
            poll_interval=self.config.poll_interval,
        )
        self._running = False
        self._sensor_task: Optional[asyncio.Task[None]] = None
        self._event_listeners: list[callable] = []

    @property
    def fsm(self) -> AsyncFSM:
        """The finite state machine."""
        return self._fsm

    @property
    def gpio(self) -> Optional[GPIOInterface]:
        """GPIO interface."""
        return self._gpio

    @property
    def sensors(self) -> Optional[TemperatureSensorInterface]:
        """Temperature sensor interface."""
        return self._sensors

    def add_event_listener(self, listener: callable) -> None:
        """Add listener for FSM events.

        Args:
            listener: Async function taking Event.
        """
        self._event_listeners.append(listener)
        self._fsm.add_listener(listener)

    async def initialize(self) -> None:
        """Initialize hardware and register state handlers."""
        # Create HAL if not provided
        if self._gpio is None or self._sensors is None:
            if self.config.use_simulator:
                gpio, sensors, model = create_hal_with_simulator()
                self._gpio = gpio
                self._sensors = sensors
                self._thermal_model = model
            else:
                self._gpio, self._sensors = create_hal()

        # Initialize HAL
        await self._gpio.setup(DEFAULT_RELAY_CONFIG)
        await self._sensors.setup(DEFAULT_SENSOR_IDS)

        # Register state handlers
        self._fsm.register_handler(IcemakerState.IDLE, self._handle_idle)
        self._fsm.register_handler(IcemakerState.POWER_ON, self._handle_power_on)
        self._fsm.register_handler(IcemakerState.CHILL, self._handle_chill)
        self._fsm.register_handler(IcemakerState.ICE, self._handle_ice)
        self._fsm.register_handler(IcemakerState.HEAT, self._handle_heat)
        self._fsm.register_handler(IcemakerState.ERROR, self._handle_error)
        self._fsm.register_handler(IcemakerState.SHUTDOWN, self._handle_shutdown)

        logger.info("Controller initialized")

    async def start(self) -> None:
        """Start the controller.

        Initializes hardware, starts the thermal model (if simulating),
        starts the sensor polling task, and runs the FSM.
        """
        await self.initialize()

        self._running = True

        # Start thermal model if simulating
        if self._thermal_model is not None:
            await self._thermal_model.start()

        # Start sensor polling
        self._sensor_task = asyncio.create_task(self._poll_sensors())

        # Run FSM (this blocks until stop() is called)
        await self._fsm.run()

    async def stop(self) -> None:
        """Stop the controller."""
        self._running = False

        # Stop FSM
        await self._fsm.stop()

        # Stop sensor polling
        if self._sensor_task is not None:
            self._sensor_task.cancel()
            try:
                await self._sensor_task
            except asyncio.CancelledError:
                pass

        # Stop thermal model
        if self._thermal_model is not None:
            await self._thermal_model.stop()

        # Turn off all relays
        if self._gpio is not None:
            await self._all_relays_off()
            await self._gpio.cleanup()

        logger.info("Controller stopped")

    async def start_cycle(self) -> bool:
        """Start an ice-making cycle from IDLE state.

        Returns:
            True if cycle started, False if not in IDLE state.
        """
        if self._fsm.state != IcemakerState.IDLE:
            return False
        return await self._fsm.transition_to(IcemakerState.CHILL)

    async def emergency_stop(self) -> None:
        """Emergency stop - turn off all relays and go to IDLE."""
        await self._all_relays_off()
        # Force transition to IDLE
        self._fsm._state = IcemakerState.IDLE
        await self._fsm._emit_event(Event(
            type=EventType.EMERGENCY_STOP,
            source="controller",
        ))

    # -------------------------------------------------------------------------
    # Relay control helpers
    # -------------------------------------------------------------------------

    async def _set_relay(self, relay: RelayName, on: bool) -> None:
        """Set relay state and emit event."""
        await self._gpio.set_relay(relay, on)
        for listener in self._event_listeners:
            await listener(relay_changed_event(relay.value, on))

    async def _all_relays_off(self) -> None:
        """Turn off all relays."""
        for relay in RelayName:
            await self._gpio.set_relay(relay, False)

    async def _set_cooling_relays(self, with_recirculation: bool = False) -> None:
        """Set relays for cooling mode."""
        await self._set_relay(RelayName.COMPRESSOR_1, True)
        await self._set_relay(RelayName.COMPRESSOR_2, True)
        await self._set_relay(RelayName.CONDENSER_FAN, True)
        await self._set_relay(RelayName.HOT_GAS_SOLENOID, False)
        await self._set_relay(RelayName.WATER_VALVE, False)
        await self._set_relay(RelayName.RECIRCULATING_PUMP, with_recirculation)

    async def _set_heating_relays(self) -> None:
        """Set relays for heating/harvest mode."""
        await self._set_relay(RelayName.COMPRESSOR_1, True)
        await self._set_relay(RelayName.COMPRESSOR_2, True)
        await self._set_relay(RelayName.CONDENSER_FAN, False)
        await self._set_relay(RelayName.HOT_GAS_SOLENOID, True)
        await self._set_relay(RelayName.WATER_VALVE, True)
        await self._set_relay(RelayName.RECIRCULATING_PUMP, False)
        await self._set_relay(RelayName.ICE_CUTTER, True)

    # -------------------------------------------------------------------------
    # Sensor polling
    # -------------------------------------------------------------------------

    async def _poll_sensors(self) -> None:
        """Background task to poll temperature sensors."""
        while self._running:
            try:
                temps = await self._sensors.read_all_temperatures()
                self._fsm.context.plate_temp = temps.get(SensorName.PLATE, 70.0)
                self._fsm.context.bin_temp = temps.get(SensorName.ICE_BIN, 70.0)

                # Emit temperature reading event
                for listener in self._event_listeners:
                    await listener(temp_reading_event(
                        self._fsm.context.plate_temp,
                        self._fsm.context.bin_temp,
                    ))

            except Exception as e:
                logger.error("Sensor polling error: %s", e)

            await asyncio.sleep(self.config.poll_interval)

    def _is_bin_full(self) -> bool:
        """Check if ice bin is full based on temperature threshold."""
        return self._fsm.context.bin_temp < self.config.bin_full_threshold

    # -------------------------------------------------------------------------
    # State handlers
    # -------------------------------------------------------------------------

    async def _handle_idle(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle IDLE state - wait for start command or bin to empty."""
        # Ensure all relays are off
        await self._all_relays_off()

        # If bin is no longer full, we could auto-start (optional)
        # For now, just wait for explicit start_cycle() call
        return None

    async def _handle_power_on(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle POWER_ON state - prime water system.

        Follows original code's startup sequence:
        1. Water valve ON for 1 minute
        2. Recirculating pump ON for 15 seconds
        3. Water valve ON for 15 seconds
        """
        elapsed = fsm.time_in_state()

        # Phase 1: Water valve (0-60s)
        if elapsed < 60:
            await self._set_relay(RelayName.WATER_VALVE, True)
            await self._set_relay(RelayName.RECIRCULATING_PUMP, False)
            return None

        # Phase 2: Pump priming (60-75s)
        if elapsed < 75:
            await self._set_relay(RelayName.WATER_VALVE, False)
            await self._set_relay(RelayName.RECIRCULATING_PUMP, True)
            return None

        # Phase 3: Final water fill (75-90s)
        if elapsed < 90:
            await self._set_relay(RelayName.RECIRCULATING_PUMP, False)
            await self._set_relay(RelayName.WATER_VALVE, True)
            return None

        # Done - transition to CHILL
        await self._set_relay(RelayName.WATER_VALVE, False)
        return IcemakerState.CHILL

    async def _handle_chill(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle CHILL state - cool plate to target temperature."""
        # Determine chill mode and parameters
        if ctx.chill_mode == "rechill":
            target_temp = self.config.rechill.target_temp
            timeout = self.config.rechill.timeout_seconds
        else:
            # Default to prechill
            ctx.chill_mode = "prechill"
            target_temp = self.config.prechill.target_temp
            timeout = self.config.prechill.timeout_seconds

        ctx.target_temp = target_temp

        # Check if we've reached target or timed out
        elapsed = fsm.time_in_state()
        if ctx.plate_temp <= target_temp:
            logger.info(
                "Chill complete: plate temp %.1f°F reached target %.1f°F",
                ctx.plate_temp,
                target_temp,
            )
            if ctx.chill_mode == "prechill":
                ctx.chill_mode = None
                ctx.cycle_start_time = datetime.now()
                return IcemakerState.ICE
            else:
                # Rechill complete - check bin and decide next action
                ctx.chill_mode = None
                ctx.cycle_count += 1
                if self._is_bin_full():
                    logger.info("Bin full, entering IDLE")
                    return IcemakerState.IDLE
                else:
                    # Start next cycle
                    ctx.chill_mode = "prechill"
                    return None  # Stay in CHILL for prechill

        if elapsed > timeout:
            logger.warning(
                "Chill timeout: %.1fs elapsed, plate temp %.1f°F (target %.1f°F)",
                elapsed,
                ctx.plate_temp,
                target_temp,
            )
            if ctx.chill_mode == "prechill":
                ctx.chill_mode = None
                return IcemakerState.ICE
            else:
                ctx.chill_mode = None
                ctx.cycle_count += 1
                if self._is_bin_full():
                    return IcemakerState.IDLE
                ctx.chill_mode = "prechill"
                return None

        # Keep cooling
        await self._set_cooling_relays(with_recirculation=False)
        return None

    async def _handle_ice(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle ICE state - make ice with recirculation."""
        target_temp = self.config.ice_making.target_temp
        timeout = self.config.ice_making.timeout_seconds
        ctx.target_temp = target_temp

        elapsed = fsm.time_in_state()

        # Check if we've reached target or timed out
        if ctx.plate_temp <= target_temp:
            logger.info(
                "Ice making complete: plate temp %.1f°F reached target %.1f°F",
                ctx.plate_temp,
                target_temp,
            )
            return IcemakerState.HEAT

        if elapsed > timeout:
            logger.warning(
                "Ice making timeout: %.1fs elapsed, plate temp %.1f°F (target %.1f°F)",
                elapsed,
                ctx.plate_temp,
                target_temp,
            )
            return IcemakerState.HEAT

        # Keep cooling with recirculation
        await self._set_cooling_relays(with_recirculation=True)
        return None

    async def _handle_heat(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle HEAT state - harvest ice."""
        target_temp = self.config.harvest.target_temp
        timeout = self.config.harvest.timeout_seconds
        ctx.target_temp = target_temp

        elapsed = fsm.time_in_state()

        # Check if we've reached target or timed out
        if ctx.plate_temp >= target_temp:
            logger.info(
                "Harvest complete: plate temp %.1f°F reached target %.1f°F",
                ctx.plate_temp,
                target_temp,
            )
            ctx.chill_mode = "rechill"
            return IcemakerState.CHILL

        if elapsed > timeout:
            logger.warning(
                "Harvest timeout: %.1fs elapsed, plate temp %.1f°F (target %.1f°F)",
                elapsed,
                ctx.plate_temp,
                target_temp,
            )
            ctx.chill_mode = "rechill"
            return IcemakerState.CHILL

        # Keep heating
        await self._set_heating_relays()
        return None

    async def _handle_error(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle ERROR state - safe shutdown and wait for reset."""
        # Turn off all relays for safety
        await self._all_relays_off()
        # Stay in error state until externally reset
        return None

    async def _handle_shutdown(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle SHUTDOWN state - graceful shutdown."""
        await self._all_relays_off()
        return IcemakerState.IDLE
