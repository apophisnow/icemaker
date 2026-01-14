"""Physics-based thermal simulation for icemaker."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from ..hal.base import RelayName, SensorName

logger = logging.getLogger(__name__)


@dataclass
class ThermalParameters:
    """Configurable thermal simulation parameters.

    All rates are in degrees Fahrenheit per second.
    These values are tuned to approximate real icemaker behavior.
    """

    # Ambient conditions
    ambient_temp_f: float = 70.0  # Room temperature
    water_input_temp_f: float = 55.0  # Cold water temperature

    # Cooling rates (degrees F per second when at ambient)
    compressor_cooling_rate: float = 0.15  # Compressor + condenser active
    compressor_only_rate: float = 0.05  # Compressor on, no condenser

    # Heating rates (degrees F per second)
    hot_gas_heating_rate: float = 0.8  # Hot gas solenoid active
    natural_warming_rate: float = 0.02  # Passive drift toward ambient

    # Water/recirculation effects
    water_cooling_effect: float = -5.0  # Temp drop from water fill
    recirculation_multiplier: float = 1.2  # Cooling enhancement factor

    # Thermal mass (affects rate of temperature change)
    # Higher = slower temperature changes
    plate_thermal_mass: float = 1.0
    bin_thermal_mass: float = 3.0  # Ice bin has more thermal inertia

    # Temperature limits
    min_temp_f: float = -10.0
    max_temp_f: float = 100.0

    # Simulation speed multiplier (for faster-than-realtime simulation)
    speed_multiplier: float = 1.0


@dataclass
class ThermalState:
    """Current state of the thermal simulation."""

    plate_temp_f: float = 70.0
    bin_temp_f: float = 70.0
    last_update: float = field(default_factory=time.monotonic)


class ThermalModel:
    """Physics-based thermal simulation for icemaker.

    Models temperature changes based on:
    - Compressor cooling effect (enhanced by condenser fan)
    - Hot gas solenoid heating
    - Water recirculation cooling enhancement
    - Natural drift toward ambient temperature
    - Thermal mass effects (plate vs bin)

    The model updates temperature based on the current relay states,
    calculating rates of change and applying them over time steps.
    """

    def __init__(self, params: Optional[ThermalParameters] = None) -> None:
        """Initialize the thermal model.

        Args:
            params: Thermal parameters. Uses defaults if None.
        """
        self.params = params or ThermalParameters()
        self.state = ThermalState()
        self._relay_states: dict[RelayName, bool] = {r: False for r in RelayName}
        self._running = False
        self._update_task: Optional[asyncio.Task[None]] = None

    def set_relay_state(self, relay: RelayName, on: bool) -> None:
        """Update relay state for thermal calculations.

        Called by the mock GPIO when relay states change.

        Args:
            relay: The relay that changed.
            on: New state (True=ON, False=OFF).
        """
        self._relay_states[relay] = on

    def get_temperature(self, sensor: SensorName) -> float:
        """Get current simulated temperature.

        Args:
            sensor: Which sensor to read.

        Returns:
            Temperature in degrees Fahrenheit.
        """
        if sensor == SensorName.PLATE:
            return self.state.plate_temp_f
        return self.state.bin_temp_f

    def _calculate_plate_rate(self) -> float:
        """Calculate plate temperature rate of change (deg F/s).

        Returns:
            Rate of temperature change for the plate.
        """
        rate = 0.0

        # Check compressor state
        compressor_on = (
            self._relay_states.get(RelayName.COMPRESSOR_1, False)
            or self._relay_states.get(RelayName.COMPRESSOR_2, False)
        )
        condenser_on = self._relay_states.get(RelayName.CONDENSER_FAN, False)

        # Cooling from compressor
        if compressor_on:
            if condenser_on:
                rate -= self.params.compressor_cooling_rate
            else:
                rate -= self.params.compressor_only_rate

        # Heating from hot gas solenoid
        if self._relay_states.get(RelayName.HOT_GAS_SOLENOID, False):
            rate += self.params.hot_gas_heating_rate

        # Recirculation pump enhances cooling (when cooling is active)
        if self._relay_states.get(RelayName.RECIRCULATING_PUMP, False):
            if rate < 0:  # Only enhances cooling, not heating
                rate *= self.params.recirculation_multiplier

        # Natural drift toward ambient (Newton's law of cooling approximation)
        temp_diff = self.params.ambient_temp_f - self.state.plate_temp_f
        rate += temp_diff * self.params.natural_warming_rate / 10.0

        # Apply thermal mass (higher mass = slower change)
        return rate / self.params.plate_thermal_mass

    def _calculate_bin_rate(self) -> float:
        """Calculate bin temperature rate of change (deg F/s).

        The bin temperature is affected by:
        - Heat transfer from the plate
        - Natural drift toward ambient

        Returns:
            Rate of temperature change for the bin.
        """
        # Plate affects bin temperature (heat transfer)
        plate_effect = (
            (self.state.plate_temp_f - self.state.bin_temp_f) * 0.005
        )

        # Ambient affects bin temperature
        ambient_effect = (
            (self.params.ambient_temp_f - self.state.bin_temp_f) * 0.002
        )

        # Apply thermal mass
        return (plate_effect + ambient_effect) / self.params.bin_thermal_mass

    def update(self, dt: float) -> None:
        """Update temperatures for a time step.

        Args:
            dt: Time step in seconds (real time, before speed multiplier).
        """
        # Apply speed multiplier
        effective_dt = dt * self.params.speed_multiplier

        # Calculate rates
        plate_rate = self._calculate_plate_rate()
        bin_rate = self._calculate_bin_rate()

        # Apply changes
        self.state.plate_temp_f += plate_rate * effective_dt
        self.state.bin_temp_f += bin_rate * effective_dt

        # Clamp to valid range
        self.state.plate_temp_f = max(
            self.params.min_temp_f,
            min(self.params.max_temp_f, self.state.plate_temp_f),
        )
        self.state.bin_temp_f = max(
            self.params.min_temp_f,
            min(self.params.max_temp_f, self.state.bin_temp_f),
        )

        self.state.last_update = time.monotonic()

    async def run(self, update_interval: float = 0.1) -> None:
        """Run continuous thermal simulation.

        Updates temperatures at the specified interval until stop() is called.

        Args:
            update_interval: Seconds between updates (real time).
        """
        self._running = True
        logger.info("Thermal simulation started")

        last_time = time.monotonic()
        while self._running:
            current_time = time.monotonic()
            dt = current_time - last_time
            self.update(dt)
            last_time = current_time

            try:
                await asyncio.sleep(update_interval)
            except asyncio.CancelledError:
                break

        logger.info("Thermal simulation stopped")

    async def start(self, update_interval: float = 0.1) -> None:
        """Start thermal simulation as a background task.

        Args:
            update_interval: Seconds between updates.
        """
        if self._update_task is not None:
            return
        self._update_task = asyncio.create_task(self.run(update_interval))

    async def stop(self) -> None:
        """Stop the thermal simulation."""
        self._running = False
        if self._update_task is not None:
            self._update_task.cancel()
            try:
                await self._update_task
            except asyncio.CancelledError:
                pass
            self._update_task = None

    def reset(
        self,
        plate_temp: float = 70.0,
        bin_temp: float = 70.0,
    ) -> None:
        """Reset simulation to initial temperatures.

        Args:
            plate_temp: Initial plate temperature.
            bin_temp: Initial bin temperature.
        """
        self.state.plate_temp_f = plate_temp
        self.state.bin_temp_f = bin_temp
        for relay in RelayName:
            self._relay_states[relay] = False
