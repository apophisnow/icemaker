"""Thermal simulation for icemaker."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from ..hal.base import RelayName, SensorName

logger = logging.getLogger(__name__)


@dataclass
class ThermalParameters:
    """Thermal simulation parameters.

    All rates are in degrees Fahrenheit per second.
    """

    # Ambient conditions
    ambient_temp_f: float = 70.0
    water_input_temp_f: float = 55.0

    # Cooling/heating rates (°F per second)
    plate_cooling_rate: float = 1.5  # Plate cooling when compressor on, no water
    water_cooling_rate: float = 0.8  # Water cooling when pump on
    plate_heating_rate: float = 1.0  # Plate heating when hot gas on
    ambient_drift_rate: float = 0.02  # Drift toward ambient when idle

    # Ice formation
    freezing_point_f: float = 32.0
    ice_growth_rate: float = 0.02  # mm/sec when plate < freezing and water at freezing
    ice_melt_rate: float = 0.1  # mm/sec when hot gas on
    max_ice_thickness_mm: float = 12.0

    # Temperature limits
    min_temp_f: float = -10.0
    max_temp_f: float = 100.0

    # Speed multiplier
    speed_multiplier: float = 1.0


@dataclass
class ThermalState:
    """Current state of the thermal simulation."""

    plate_temp_f: float = 70.0
    bin_temp_f: float = 70.0
    water_temp_f: float = 70.0
    ice_thickness_mm: float = 0.0
    last_update: float = field(default_factory=time.monotonic)


class ThermalModel:
    """Simple thermal simulation for icemaker.

    Models the key thermal behaviors:
    1. Prechill: Plate cools directly (no water) from 70°F to 32°F
    2. Ice making: Water cools to 32°F, then ice forms, plate drops below freezing
    3. Harvest: Hot gas heats plate, ice melts off
    4. Rechill: Similar to prechill but starting warmer
    """

    def __init__(self, params: Optional[ThermalParameters] = None) -> None:
        self.params = params or ThermalParameters()
        self.state = ThermalState()
        self._relay_states: dict[RelayName, bool] = {r: False for r in RelayName}
        self._running = False
        self._update_task: Optional[asyncio.Task[None]] = None

    def set_relay_state(self, relay: RelayName, on: bool) -> None:
        """Update relay state for thermal calculations."""
        self._relay_states[relay] = on

    def get_temperature(self, sensor: SensorName) -> float:
        """Get current simulated temperature."""
        if sensor == SensorName.PLATE:
            return self.state.plate_temp_f
        return self.state.bin_temp_f

    def _is_compressor_on(self) -> bool:
        return (
            self._relay_states.get(RelayName.COMPRESSOR_1, False)
            or self._relay_states.get(RelayName.COMPRESSOR_2, False)
        )

    def _is_hot_gas_on(self) -> bool:
        return self._relay_states.get(RelayName.HOT_GAS_SOLENOID, False)

    def _is_pump_on(self) -> bool:
        return self._relay_states.get(RelayName.RECIRCULATING_PUMP, False)

    def _is_water_valve_on(self) -> bool:
        return self._relay_states.get(RelayName.WATER_VALVE, False)

    def update(self, dt: float) -> None:
        """Update temperatures for a time step."""
        effective_dt = dt * self.params.speed_multiplier
        p = self.params
        s = self.state

        compressor_on = self._is_compressor_on()
        hot_gas_on = self._is_hot_gas_on()
        pump_on = self._is_pump_on()
        water_valve_on = self._is_water_valve_on()

        # --- Water temperature ---
        if water_valve_on:
            # Fresh water coming in, mix toward input temp
            s.water_temp_f += (p.water_input_temp_f - s.water_temp_f) * 0.5 * effective_dt

        if pump_on and compressor_on and not hot_gas_on:
            # Water is being cooled by refrigeration
            s.water_temp_f -= p.water_cooling_rate * effective_dt
            # Water can't go below freezing
            s.water_temp_f = max(p.freezing_point_f, s.water_temp_f)

        # Water drifts toward ambient when not being actively cooled
        if not (pump_on and compressor_on):
            s.water_temp_f += (p.ambient_temp_f - s.water_temp_f) * 0.01 * effective_dt

        # --- Plate temperature ---
        if hot_gas_on and compressor_on:
            # Heating mode - plate heats up
            s.plate_temp_f += p.plate_heating_rate * effective_dt
            # Melt ice
            s.ice_thickness_mm = max(0, s.ice_thickness_mm - p.ice_melt_rate * effective_dt)

        elif compressor_on:
            if pump_on:
                # Ice making mode - plate temp tied to water temp until water freezes
                if s.water_temp_f > p.freezing_point_f:
                    # Water still warm - plate follows water temp
                    s.plate_temp_f += (s.water_temp_f - s.plate_temp_f) * 0.5 * effective_dt
                else:
                    # Water at freezing point - ice can form, plate can go colder
                    # Plate cools, but slower than direct cooling
                    s.plate_temp_f -= p.plate_cooling_rate * 0.5 * effective_dt
                    # Ice grows when plate is below freezing
                    if s.plate_temp_f < p.freezing_point_f:
                        s.ice_thickness_mm += p.ice_growth_rate * effective_dt
                        s.ice_thickness_mm = min(s.ice_thickness_mm, p.max_ice_thickness_mm)
            else:
                # Prechill/rechill mode - direct plate cooling, no water
                s.plate_temp_f -= p.plate_cooling_rate * effective_dt

        else:
            # Compressor off - drift toward ambient
            drift = (p.ambient_temp_f - s.plate_temp_f) * p.ambient_drift_rate * effective_dt
            s.plate_temp_f += drift

        # --- Bin temperature ---
        # Bin slowly drifts toward ambient (ice melts)
        s.bin_temp_f += (p.ambient_temp_f - s.bin_temp_f) * 0.005 * effective_dt

        # Clamp temperatures
        s.plate_temp_f = max(p.min_temp_f, min(p.max_temp_f, s.plate_temp_f))
        s.bin_temp_f = max(p.min_temp_f, min(p.max_temp_f, s.bin_temp_f))
        s.water_temp_f = max(p.freezing_point_f, min(p.max_temp_f, s.water_temp_f))

        s.last_update = time.monotonic()

    async def run(self, update_interval: float = 0.1) -> None:
        """Run continuous thermal simulation."""
        self._running = True
        logger.info("Thermal simulation started (speed: %.1fx)", self.params.speed_multiplier)

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
        """Start thermal simulation as a background task."""
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
        """Reset simulation to initial temperatures."""
        self.state.plate_temp_f = plate_temp
        self.state.bin_temp_f = bin_temp
        self.state.water_temp_f = water_temp
        self.state.ice_thickness_mm = 0.0
        for relay in RelayName:
            self._relay_states[relay] = False

    def get_water_temp(self) -> float:
        """Get current water reservoir temperature."""
        return self.state.water_temp_f

    def get_ice_thickness(self) -> float:
        """Get current ice thickness on the plate."""
        return self.state.ice_thickness_mm

    def set_speed_multiplier(self, multiplier: float) -> None:
        """Set the simulation speed multiplier."""
        multiplier = max(0.1, min(1000.0, multiplier))
        self.params.speed_multiplier = multiplier
        logger.info("Simulation speed set to %.1fx", multiplier)

    def get_speed_multiplier(self) -> float:
        """Get the current simulation speed multiplier."""
        return self.params.speed_multiplier
