"""Main controller orchestrating FSM, HAL, and state handlers."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

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
from ..simulator.physics_model import PhysicsSimulator
from .events import Event, EventType, relay_changed_event, temp_reading_event
from .fsm import AsyncFSM, FSMContext
from .states import ChillMode, IcemakerState

logger = logging.getLogger(__name__)


class IcemakerController:
    """Main controller for icemaker operation.

    Orchestrates the FSM, HAL interfaces, and implements state handlers
    that control relay states based on temperature readings.

    The controller implements the ice-making cycle:
    0. OFF: System powered off
    1. POWER_ON: Prime water system (optional, skipped by default)
    2. STANDBY: Waiting for manual start_cycle() call
    3. CHILL (prechill): Cool plate to 32°F
    4. ICE: Make ice at -2°F with recirculation
    5. HEAT: Harvest ice at 38°F
    6. CHILL (rechill): Cool to 35°F
    7. Check bin:
       - Bin full: IDLE (auto-restarts when bin empties)
       - Bin not full: repeat cycle

    STANDBY vs IDLE:
    - STANDBY: Manual control - waits for explicit start_cycle()
    - IDLE: Active ice-making paused - auto-restarts when bin empties

    Priming can be enabled via power_on(prime=True) or config.priming_enabled=True.
    """

    def __init__(
        self,
        config: Optional[IcemakerConfig] = None,
        gpio: Optional[GPIOInterface] = None,
        sensors: Optional[TemperatureSensorInterface] = None,
        thermal_model: Optional[PhysicsSimulator] = None,
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
            initial_state=IcemakerState.OFF,
            poll_interval=self.config.poll_interval,
        )
        self._running = False
        self._sensor_task: Optional[asyncio.Task[None]] = None
        self._event_listeners: list[callable] = []
        self._shutdown_requested = False  # Graceful shutdown flag

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

    @property
    def shutdown_requested(self) -> bool:
        """Whether a graceful shutdown has been requested."""
        return self._shutdown_requested

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
                # Apply speed multiplier from config
                self._thermal_model.set_speed_multiplier(self.config.simulator_speed)
            else:
                self._gpio, self._sensors = create_hal()

        # Initialize HAL
        await self._gpio.setup(DEFAULT_RELAY_CONFIG)
        await self._sensors.setup(DEFAULT_SENSOR_IDS)

        # Connect FSM to simulated time if using simulator
        if self._thermal_model is not None:
            self._fsm.set_simulated_time_getter(self._thermal_model.get_simulated_time)

        # Register state handlers
        self._fsm.register_handler(IcemakerState.OFF, self._handle_off)
        self._fsm.register_handler(IcemakerState.STANDBY, self._handle_standby)
        self._fsm.register_handler(IcemakerState.IDLE, self._handle_idle)
        self._fsm.register_handler(IcemakerState.POWER_ON, self._handle_power_on)
        self._fsm.register_handler(IcemakerState.CHILL, self._handle_chill)
        self._fsm.register_handler(IcemakerState.ICE, self._handle_ice)
        self._fsm.register_handler(IcemakerState.HEAT, self._handle_heat)
        self._fsm.register_handler(IcemakerState.ERROR, self._handle_error)
        self._fsm.register_handler(IcemakerState.SHUTDOWN, self._handle_shutdown)
        self._fsm.register_handler(IcemakerState.DIAGNOSTIC, self._handle_diagnostic)

        # Load persistent cycle count
        self._load_cycle_count()

        logger.info("Controller initialized")

    def _get_cycle_count_path(self) -> Path:
        """Get path to the cycle count file."""
        data_dir = Path(self.config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "cycle_count.txt"

    def _load_cycle_count(self) -> None:
        """Load lifetime cycle count from persistent storage."""
        path = self._get_cycle_count_path()
        try:
            if path.exists():
                count = int(path.read_text().strip())
                self._fsm.context.cycle_count = count
                logger.info("Loaded lifetime cycle count: %d", count)
            else:
                logger.info("No existing cycle count file, starting at 0")
        except (ValueError, OSError) as e:
            logger.warning("Failed to load cycle count: %s", e)

    def _save_cycle_count(self) -> None:
        """Save lifetime cycle count to persistent storage."""
        path = self._get_cycle_count_path()
        try:
            path.write_text(str(self._fsm.context.cycle_count))
            logger.debug("Saved cycle count: %d", self._fsm.context.cycle_count)
        except OSError as e:
            logger.warning("Failed to save cycle count: %s", e)

    def _get_state_path(self) -> Path:
        """Get path to the state persistence file."""
        data_dir = Path(self.config.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir / "state.json"

    async def _save_state(self) -> None:
        """Save current state for graceful restart.

        Saves FSM state, relay states, and context to enable
        resuming operation after a restart without changing relay states.
        """
        if self._gpio is None:
            return

        path = self._get_state_path()
        try:
            relay_states = await self._gpio.get_all_relays()
            ctx = self._fsm.context

            state_data: dict[str, Any] = {
                "version": 1,
                "timestamp": datetime.now().isoformat(),
                "fsm_state": self._fsm.state.value,
                "previous_state": (
                    self._fsm.previous_state.value if self._fsm.previous_state else None
                ),
                "relays": {name.value: on for name, on in relay_states.items()},
                "context": {
                    "plate_temp": ctx.plate_temp,
                    "bin_temp": ctx.bin_temp,
                    "target_temp": ctx.target_temp,
                    "cycle_count": ctx.cycle_count,
                    "chill_mode": ctx.chill_mode,
                    "state_enter_time": ctx.state_enter_time.isoformat(),
                    "cycle_start_time": (
                        ctx.cycle_start_time.isoformat() if ctx.cycle_start_time else None
                    ),
                },
            }

            path.write_text(json.dumps(state_data, indent=2))
            logger.info("Saved state for graceful restart: %s", self._fsm.state.name)
        except (OSError, TypeError) as e:
            logger.warning("Failed to save state: %s", e)

    async def _load_and_restore_state(self) -> bool:
        """Load and restore state from a previous run.

        Restores relay states immediately to maintain hardware state,
        then restores FSM state and context.

        Returns:
            True if state was restored, False if no valid state found.
        """
        path = self._get_state_path()
        if not path.exists():
            logger.info("No saved state found, starting fresh")
            return False

        try:
            state_data = json.loads(path.read_text())

            # Validate version
            if state_data.get("version") != 1:
                logger.warning("Unknown state file version, ignoring")
                return False

            # Restore relay states FIRST (before FSM runs)
            if self._gpio is not None and "relays" in state_data:
                for relay_name, on in state_data["relays"].items():
                    try:
                        relay = RelayName(relay_name)
                        await self._set_relay(relay, on)
                        logger.debug("Restored relay %s = %s", relay_name, on)
                    except ValueError:
                        logger.warning("Unknown relay in saved state: %s", relay_name)

            # Restore FSM state
            fsm_state_name = state_data.get("fsm_state")
            if fsm_state_name:
                try:
                    restored_state = IcemakerState(fsm_state_name)
                    self._fsm._state = restored_state
                    logger.info("Restored FSM state: %s", restored_state.name)
                except ValueError:
                    logger.warning("Unknown FSM state in saved state: %s", fsm_state_name)

            # Restore previous state
            prev_state_name = state_data.get("previous_state")
            if prev_state_name:
                try:
                    self._fsm._previous_state = IcemakerState(prev_state_name)
                except ValueError:
                    pass

            # Restore context
            ctx_data = state_data.get("context", {})
            ctx = self._fsm.context
            ctx.plate_temp = ctx_data.get("plate_temp", 70.0)
            ctx.bin_temp = ctx_data.get("bin_temp", 70.0)
            ctx.target_temp = ctx_data.get("target_temp", 32.0)
            ctx.cycle_count = ctx_data.get("cycle_count", 0)
            ctx.chill_mode = ctx_data.get("chill_mode")

            if ctx_data.get("state_enter_time"):
                ctx.state_enter_time = datetime.fromisoformat(ctx_data["state_enter_time"])
            if ctx_data.get("cycle_start_time"):
                ctx.cycle_start_time = datetime.fromisoformat(ctx_data["cycle_start_time"])

            # Remove state file after successful restore
            path.unlink()
            logger.info("State restored successfully, removed state file")
            return True

        except (json.JSONDecodeError, OSError, KeyError) as e:
            logger.warning("Failed to restore state: %s", e)
            return False

    def _clear_saved_state(self) -> None:
        """Remove the saved state file (used after clean shutdown)."""
        path = self._get_state_path()
        try:
            if path.exists():
                path.unlink()
        except OSError:
            pass

    async def start(self) -> None:
        """Start the controller.

        Initializes hardware, starts the thermal model (if simulating),
        starts the sensor polling task, and runs the FSM.

        If a previous graceful shutdown left a saved state, relay states
        and FSM state will be restored automatically.
        """
        await self.initialize()

        # Try to restore state from a previous graceful shutdown
        restored = await self._load_and_restore_state()

        self._running = True

        # Start thermal model if simulating
        if self._thermal_model is not None:
            await self._thermal_model.start()

        # Start sensor polling
        self._sensor_task = asyncio.create_task(self._poll_sensors())

        if restored:
            logger.info("Resuming from restored state: %s", self._fsm.state.name)

        # Run FSM (this blocks until stop() is called)
        await self._fsm.run()

    async def stop(self, graceful: bool = False) -> None:
        """Stop the controller.

        Args:
            graceful: If True, save state for restart without changing relays.
                     If False (default), turn off all relays and do full shutdown.
        """
        if graceful:
            # Save state BEFORE stopping anything
            await self._save_state()
            logger.info("Graceful shutdown: state saved, relays will be preserved on restart")

        self._running = False

        # Stop FSM (skip transition to SHUTDOWN in graceful mode)
        if graceful:
            self._fsm._running = False
        else:
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

        # Handle relays based on shutdown mode
        if self._gpio is not None:
            if graceful:
                # Don't turn off relays - just cleanup GPIO without state changes
                await self._gpio.cleanup()
            else:
                # Full shutdown - turn off all relays
                await self._all_relays_off()
                await self._gpio.cleanup()
                self._clear_saved_state()

        logger.info("Controller stopped (graceful=%s)", graceful)

    async def power_on(self, prime: bool | None = None) -> bool:
        """Power on the icemaker from OFF state.

        Args:
            prime: Whether to run the water priming sequence.
                   If None (default), uses config.priming_enabled setting.
                   If True, always runs priming sequence.
                   If False, skips priming and goes directly to STANDBY.

        Returns:
            True if power on started, False if not in OFF state.
        """
        if self._fsm.state != IcemakerState.OFF:
            return False

        # Determine whether to prime based on parameter or config
        should_prime = prime if prime is not None else self.config.priming_enabled

        if should_prime:
            logger.info("Power on with water priming sequence")
            return await self._fsm.transition_to(IcemakerState.POWER_ON)
        else:
            logger.info("Power on skipping priming sequence")
            return await self._fsm.transition_to(IcemakerState.STANDBY)

    async def power_off(self) -> bool:
        """Power off the icemaker.

        If in STANDBY, IDLE, or ERROR: transitions directly to OFF.
        If in an active cycle (CHILL, ICE, HEAT): sets shutdown flag.
        The cycle will complete through harvest then go to STANDBY,
        which will auto-transition to OFF after the standby timeout.

        Returns:
            True if shutdown initiated, False if not in a valid state.
        """
        # Direct shutdown from non-cycle states
        if self._fsm.state in {IcemakerState.STANDBY, IcemakerState.IDLE, IcemakerState.ERROR}:
            self._shutdown_requested = False  # Clear flag if set
            return await self._fsm.transition_to(IcemakerState.OFF)

        # Graceful shutdown from cycle states
        cycle_states = {IcemakerState.CHILL, IcemakerState.ICE, IcemakerState.HEAT}
        if self._fsm.state in cycle_states:
            logger.info("Graceful shutdown requested - will complete cycle then power off")
            self._shutdown_requested = True
            return True

        return False

    async def start_cycle(self) -> bool:
        """Start an ice-making cycle from STANDBY or IDLE state.

        Returns:
            True if cycle started, False if not in a valid state.
        """
        if self._fsm.state not in {IcemakerState.STANDBY, IcemakerState.IDLE}:
            return False
        self._fsm.context.chill_mode = "prechill"
        self._fsm.context.cycle_start_time = datetime.now()
        return await self._fsm.transition_to(IcemakerState.CHILL)

    async def stop_cycle(self) -> bool:
        """Stop the current ice-making cycle and return to STANDBY.

        Can be called from CHILL, ICE, HEAT, or IDLE states.
        Use start_cycle() to begin a new cycle from STANDBY.

        Returns:
            True if stopped, False if not in an active cycle state.
        """
        active_states = {
            IcemakerState.CHILL,
            IcemakerState.ICE,
            IcemakerState.HEAT,
            IcemakerState.IDLE,
        }
        if self._fsm.state not in active_states:
            return False
        return await self._fsm.transition_to(IcemakerState.STANDBY)

    async def emergency_stop(self) -> None:
        """Emergency stop - turn off all relays and go to OFF."""
        await self._all_relays_off()
        # Force transition to OFF
        self._fsm._state = IcemakerState.OFF
        await self._fsm._emit_event(Event(
            type=EventType.EMERGENCY_STOP,
            source="controller",
        ))

    async def enter_diagnostic(self) -> bool:
        """Enter diagnostic mode from OFF state.

        In diagnostic mode, relays can be manually controlled via the API.
        The FSM does not automatically control any relays.

        Returns:
            True if entered diagnostic mode, False if not in OFF state.
        """
        if self._fsm.state != IcemakerState.OFF:
            return False
        logger.info("Entering diagnostic mode")
        return await self._fsm.transition_to(IcemakerState.DIAGNOSTIC)

    async def exit_diagnostic(self) -> bool:
        """Exit diagnostic mode and return to OFF state.

        All relays will be turned off.

        Returns:
            True if exited diagnostic mode, False if not in DIAGNOSTIC state.
        """
        if self._fsm.state != IcemakerState.DIAGNOSTIC:
            return False
        logger.info("Exiting diagnostic mode")
        await self._all_relays_off()
        return await self._fsm.transition_to(IcemakerState.OFF)

    # -------------------------------------------------------------------------
    # Relay control helpers
    # -------------------------------------------------------------------------

    async def _set_relay(self, relay: RelayName, on: bool) -> None:
        """Set relay state and emit event."""
        await self._gpio.set_relay(relay, on)
        for listener in self._event_listeners:
            await listener(relay_changed_event(relay.value, on))

    async def _all_relays_off(self) -> None:
        """Turn off all relays and emit events."""
        for relay in RelayName:
            await self._set_relay(relay, False)

    async def _set_cooling_relays(self, with_recirculation: bool = False) -> None:
        """Set relays for cooling mode."""
        await self._set_relay(RelayName.COMPRESSOR_1, True)
        await self._set_relay(RelayName.COMPRESSOR_2, True)
        await self._set_relay(RelayName.CONDENSER_FAN, True)
        await self._set_relay(RelayName.HOT_GAS_SOLENOID, False)
        await self._set_relay(RelayName.WATER_VALVE, False)
        await self._set_relay(RelayName.RECIRCULATING_PUMP, with_recirculation)
        await self._set_relay(RelayName.ICE_CUTTER, True)  # Ice cutter ON during cycle

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

    async def _handle_off(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle OFF state - system powered off."""
        # Clear shutdown flag since we've reached OFF
        self._shutdown_requested = False
        # Ensure all relays are off
        await self._all_relays_off()
        # Wait for explicit power_on() call
        return None

    async def _handle_standby(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle STANDBY state - powered on, waiting for manual start.

        Unlike IDLE, STANDBY does NOT auto-restart when bin empties.
        User must explicitly call start_cycle() to begin ice making.

        Ice cutter stays ON during standby to ensure any remaining ice is cut.
        Auto-transitions to OFF after standby_timeout if shutdown was requested.
        """
        # Turn off all relays except ice cutter
        await self._set_relay(RelayName.WATER_VALVE, False)
        await self._set_relay(RelayName.HOT_GAS_SOLENOID, False)
        await self._set_relay(RelayName.RECIRCULATING_PUMP, False)
        await self._set_relay(RelayName.COMPRESSOR_1, False)
        await self._set_relay(RelayName.COMPRESSOR_2, False)
        await self._set_relay(RelayName.CONDENSER_FAN, False)
        # Keep ice cutter ON
        await self._set_relay(RelayName.ICE_CUTTER, True)

        # Check for standby timeout (auto-transition to OFF)
        elapsed = fsm.time_in_state()
        if elapsed >= self.config.standby_timeout:
            logger.info(
                "Standby timeout (%.1fs), transitioning to OFF",
                elapsed,
            )
            self._shutdown_requested = False  # Clear flag
            return IcemakerState.OFF

        # Wait for explicit start_cycle() or power_off() call
        return None

    async def _handle_idle(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle IDLE state - powered on, ready to make ice.

        If we entered IDLE because the bin was full, periodically check
        if the bin has emptied enough to resume ice making.
        Following mark_icemaker2.py: check every minute, restart when bin_temp >= threshold.
        """
        # Ensure all relays are off while idle
        await self._all_relays_off()

        # Check if bin has emptied enough to resume
        # bin_full returns True when temp < threshold (35°F)
        # So when temp >= threshold, bin is NOT full and we can restart
        if not self._is_bin_full():
            logger.info(
                "Bin no longer full (temp %.1f°F >= %.1f°F), restarting ice cycle",
                ctx.bin_temp,
                self.config.bin_full_threshold,
            )
            ctx.chill_mode = "prechill"
            ctx.cycle_start_time = datetime.now()
            return IcemakerState.CHILL

        # Stay in IDLE, waiting for bin to empty or manual start
        return None

    async def _handle_power_on(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle POWER_ON state - prime water system.

        Runs the priming sequence in 3 configurable phases:
        1. Water valve ON (flush/rinse lines)
        2. Recirculating pump ON (prime pump)
        3. Water valve ON (fill reservoir)
        """
        elapsed = fsm.time_in_state()
        priming = self.config.priming

        phase1_end = priming.flush_time_seconds
        phase2_end = phase1_end + priming.pump_time_seconds
        phase3_end = phase2_end + priming.fill_time_seconds

        # Phase 1: Flush/rinse water lines
        if elapsed < phase1_end:
            await self._set_relay(RelayName.WATER_VALVE, True)
            await self._set_relay(RelayName.RECIRCULATING_PUMP, False)
            return None

        # Phase 2: Prime the pump
        if elapsed < phase2_end:
            await self._set_relay(RelayName.WATER_VALVE, False)
            await self._set_relay(RelayName.RECIRCULATING_PUMP, True)
            return None

        # Phase 3: Fill reservoir
        if elapsed < phase3_end:
            await self._set_relay(RelayName.RECIRCULATING_PUMP, False)
            await self._set_relay(RelayName.WATER_VALVE, True)
            return None

        # Done - transition to STANDBY (ready for user to start cycle)
        await self._set_relay(RelayName.WATER_VALVE, False)
        return IcemakerState.STANDBY

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

        # Set relays FIRST, before checking conditions
        await self._set_cooling_relays(with_recirculation=False)

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
                # Rechill complete - check shutdown flag, bin, and decide next action
                ctx.chill_mode = None
                ctx.cycle_count += 1
                ctx.session_cycle_count += 1
                self._save_cycle_count()

                # Check for graceful shutdown request
                if self._shutdown_requested:
                    logger.info("Graceful shutdown: cycle complete, entering STANDBY")
                    return IcemakerState.STANDBY

                if self._is_bin_full():
                    logger.info("Bin full (temp %.1f°F < %.1f°F), entering IDLE to wait",
                                ctx.bin_temp, self.config.bin_full_threshold)
                    # Go to IDLE - it will poll and auto-restart when bin empties
                    return IcemakerState.IDLE
                else:
                    # Bin not full - start next cycle immediately
                    logger.info("Bin not full (temp %.1f°F), starting next cycle",
                                ctx.bin_temp)
                    ctx.chill_mode = "prechill"
                    ctx.cycle_start_time = datetime.now()
                    return IcemakerState.ICE

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
                ctx.session_cycle_count += 1
                self._save_cycle_count()

                # Check for graceful shutdown request
                if self._shutdown_requested:
                    logger.info("Graceful shutdown: cycle complete (timeout), entering STANDBY")
                    return IcemakerState.STANDBY

                if self._is_bin_full():
                    return IcemakerState.IDLE
                # Start next cycle - transition to ICE state
                ctx.chill_mode = "prechill"
                ctx.cycle_start_time = datetime.now()
                return IcemakerState.ICE

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

        # Set relays FIRST, before checking conditions
        await self._set_cooling_relays(with_recirculation=True)

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

        return None

    async def _handle_heat(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle HEAT state - harvest ice.

        Per reference implementation:
        - Condenser fan OFF, recirculating pump OFF
        - Water valve ON for harvest_fill_time seconds (to refill reservoir)
        - Hot gas solenoid ON (heats plate to release ice)
        - Ice cutter ON
        - Compressors stay ON (from ice making phase)
        """
        target_temp = self.config.harvest.target_temp
        timeout = self.config.harvest.timeout_seconds
        fill_time = self.config.harvest_fill_time
        ctx.target_temp = target_temp

        elapsed = fsm.time_in_state()

        # Set heating relays, but control water valve based on fill time
        await self._set_relay(RelayName.COMPRESSOR_1, True)
        await self._set_relay(RelayName.COMPRESSOR_2, True)
        await self._set_relay(RelayName.CONDENSER_FAN, False)
        await self._set_relay(RelayName.HOT_GAS_SOLENOID, True)
        await self._set_relay(RelayName.RECIRCULATING_PUMP, False)
        await self._set_relay(RelayName.ICE_CUTTER, True)
        # Water valve only runs for the first fill_time seconds
        await self._set_relay(RelayName.WATER_VALVE, elapsed < fill_time)

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
        return IcemakerState.OFF

    async def _handle_diagnostic(
        self,
        fsm: AsyncFSM,
        ctx: FSMContext,
    ) -> Optional[IcemakerState]:
        """Handle DIAGNOSTIC state - manual relay control mode.

        In this state, relays are not automatically controlled.
        Users can manually toggle relays via the API for testing purposes.
        """
        # No automatic relay control - relays are controlled via API
        # Just wait for exit_diagnostic() call
        return None
