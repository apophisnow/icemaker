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
    water_input_temp_f: float = 55.0  # Fresh water temperature from valve

    # Cooling rates (degrees F per second when at ambient)
    compressor_cooling_rate: float = 11.75  # Compressor + condenser active
    compressor_only_rate: float = 12.7  # Compressor on, no condenser

    # Heating rates (degrees F per second)
    hot_gas_heating_rate: float = 10.8  # Hot gas solenoid active
    natural_warming_rate: float = 0.02  # Passive drift toward ambient

    # Water/recirculation heat transfer
    water_plate_transfer_rate: float = 0.3  # Heat transfer coefficient plate<->water

    # Water reservoir parameters
    reservoir_volume_oz: float = 32.0  # Reservoir capacity in fluid ounces
    valve_flow_rate_oz_per_sec: float = 2.0  # Water valve flow rate (fills in ~16 sec)

    # Thermal mass (affects rate of temperature change)
    # Higher = slower temperature changes
    plate_thermal_mass: float = 1.0
    bin_thermal_mass: float = 3.0  # Ice bin has more thermal inertia

    # Temperature limits
    min_temp_f: float = -10.0
    max_temp_f: float = 100.0
    freezing_point_f: float = 32.0  # Water freezes here

    # Simulation speed multiplier (for faster-than-realtime simulation)
    speed_multiplier: float = 1.0


@dataclass
class ThermalState:
    """Current state of the thermal simulation."""

    plate_temp_f: float = 70.0
    bin_temp_f: float = 70.0
    water_temp_f: float = 70.0  # Water reservoir starts at room temp
    water_volume_oz: float = 32.0  # Current water in reservoir
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

        # Check relay states
        compressor_on = (
            self._relay_states.get(RelayName.COMPRESSOR_1, False)
            or self._relay_states.get(RelayName.COMPRESSOR_2, False)
        )
        condenser_on = self._relay_states.get(RelayName.CONDENSER_FAN, False)
        hot_gas_on = self._relay_states.get(RelayName.HOT_GAS_SOLENOID, False)

        # Hot gas solenoid redirects hot refrigerant to the plate for heating
        # When hot gas is ON, compressor provides heat instead of cooling
        if hot_gas_on and compressor_on:
            # Hot gas bypass: compressor pumps hot refrigerant directly to plate
            rate += self.params.hot_gas_heating_rate
        elif compressor_on:
            # Normal cooling mode (efficiency decreases at higher ambient temps)
            ambient_penalty = max(0, (self.params.ambient_temp_f - 70.0) * 0.02)
            efficiency = max(0.5, 1.0 - ambient_penalty)  # Floor at 50% efficiency

            if condenser_on:
                rate -= self.params.compressor_cooling_rate * efficiency
            else:
                rate -= self.params.compressor_only_rate * efficiency

        # Recirculation pump causes heat transfer between plate and water
        if self._relay_states.get(RelayName.RECIRCULATING_PUMP, False):
            water_plate_diff = self.state.water_temp_f - self.state.plate_temp_f
            rate += water_plate_diff * self.params.water_plate_transfer_rate

        # Natural drift toward ambient (Newton's law of cooling approximation)
        temp_diff = self.params.ambient_temp_f - self.state.plate_temp_f
        rate += temp_diff * self.params.natural_warming_rate / 10.0

        # Apply thermal mass (higher mass = slower change)
        return rate / self.params.plate_thermal_mass

    def _update_water_reservoir(self, dt: float) -> None:
        """Update water reservoir temperature and volume.

        Models a physical reservoir where:
        - Water valve adds fresh water at input temp, displacing existing water
          (passive overflow drain)
        - Recirculation transfers heat between plate and water
        - Water at freezing point leaves as ice on the plate

        Args:
            dt: Effective time step in seconds (after speed multiplier).
        """
        # Handle water valve - fresh water displaces old water
        if self._relay_states.get(RelayName.WATER_VALVE, False):
            # Calculate how much fresh water enters this timestep
            fresh_water_oz = self.params.valve_flow_rate_oz_per_sec * dt
            reservoir_vol = self.params.reservoir_volume_oz

            # Mix fresh water with existing - weighted average by volume
            # Fresh water displaces old (overflow drain), so total stays at reservoir_volume
            if fresh_water_oz >= reservoir_vol:
                # Complete replacement
                self.state.water_temp_f = self.params.water_input_temp_f
            else:
                # Partial mixing: weighted average by volume
                # new_temp = (old_vol * old_temp + fresh_vol * fresh_temp) / total
                old_water_oz = reservoir_vol - fresh_water_oz
                self.state.water_temp_f = (
                    (old_water_oz * self.state.water_temp_f)
                    + (fresh_water_oz * self.params.water_input_temp_f)
                ) / reservoir_vol

        # Recirculation pump causes heat transfer between water and plate
        if self._relay_states.get(RelayName.RECIRCULATING_PUMP, False):
            plate_water_diff = self.state.plate_temp_f - self.state.water_temp_f
            self.state.water_temp_f += plate_water_diff * self.params.water_plate_transfer_rate * dt

        # Natural drift toward ambient (slower than plate)
        ambient_diff = self.params.ambient_temp_f - self.state.water_temp_f
        self.state.water_temp_f += ambient_diff * self.params.natural_warming_rate / 20.0 * dt

        # Water can't go below freezing (it becomes ice and leaves the reservoir)
        self.state.water_temp_f = max(
            self.params.freezing_point_f, self.state.water_temp_f
        )

    def _calculate_bin_rate(self) -> float:
        """Calculate bin temperature rate of change (deg F/s).

        The bin temperature is affected by:
        - Heat transfer from the plate
        - Natural drift toward ambient (bin is NOT refrigerated, so melting occurs)

        Returns:
            Rate of temperature change for the bin.
        """
        # Plate affects bin temperature (heat transfer)
        plate_effect = (
            (self.state.plate_temp_f - self.state.bin_temp_f) * 0.005
        )

        # Ambient affects bin temperature (higher rate since bin is unrefrigerated)
        # Ice melts faster at higher room temps per the manual
        ambient_effect = (
            (self.params.ambient_temp_f - self.state.bin_temp_f) * 0.008
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

        # Calculate rates for plate and bin
        plate_rate = self._calculate_plate_rate()
        bin_rate = self._calculate_bin_rate()

        # Apply changes to plate and bin
        self.state.plate_temp_f += plate_rate * effective_dt
        self.state.bin_temp_f += bin_rate * effective_dt

        # Update water reservoir (volume-based mixing model)
        self._update_water_reservoir(effective_dt)

        # Clamp plate and bin to valid range
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
        water_temp: float = 70.0,
    ) -> None:
        """Reset simulation to initial temperatures.

        Args:
            plate_temp: Initial plate temperature.
            bin_temp: Initial bin temperature.
            water_temp: Initial water reservoir temperature.
        """
        self.state.plate_temp_f = plate_temp
        self.state.bin_temp_f = bin_temp
        self.state.water_temp_f = water_temp
        self.state.water_volume_oz = self.params.reservoir_volume_oz
        for relay in RelayName:
            self._relay_states[relay] = False
