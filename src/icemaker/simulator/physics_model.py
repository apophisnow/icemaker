"""Physics-based thermal simulation for icemaker.

This module provides a realistic physics simulation with discrete thermal bodies
(Reservoir, CoolingPlate) that interact through heat transfer equations.

The simulation uses fixed-size ticks for deterministic behavior regardless of
speed multiplier. Each tick advances simulated time by TICK_SIZE_SECONDS.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from ..hal.base import RelayName, SensorName

logger = logging.getLogger(__name__)

# Fixed tick size for deterministic simulation (1 second per tick)
TICK_SIZE_SECONDS: float = 1.0

# Maximum ticks per update call to prevent runaway physics at high speeds
# At 100x speed with 50ms update interval, we'd process 5 ticks per update
# At 1000x speed, we cap at 100 ticks to prevent physics instability
MAX_TICKS_PER_UPDATE: int = 100


def fahrenheit_to_kelvin(f: float) -> float:
    """Convert Fahrenheit to Kelvin."""
    return (f - 32) * 5 / 9 + 273.15


def kelvin_to_fahrenheit(k: float) -> float:
    """Convert Kelvin to Fahrenheit."""
    return (k - 273.15) * 9 / 5 + 32


@dataclass
class SimulatorParams:
    """Parameters for the physics simulation.

    All temperatures in Fahrenheit, heat transfer coefficients in W/(m²·K),
    areas in m², flow rates in L/s.

    The ice-making simulation models realistic ice formation:
    - Water cools until it reaches 32°F (freezing point)
    - At 32°F, latent heat of fusion absorbs energy while ice forms on plate
    - Ice layer thickness is tracked; thicker ice insulates the plate from water
    - Plate continues to cool as ice builds, dropping below 32°F
    - Plate temperature indicates ice thickness (colder = thicker ice)

    Default values are tuned so that:
    - Prechill (70°F -> 32°F): ~100s (timeout 120s)
    - Ice making (ice builds, plate drops to -2°F): ~1200s (timeout 1500s)
    - Harvest (-2°F -> 38°F): ~180s (timeout 240s)
    - Rechill (38°F -> 35°F): ~10s (timeout 300s)
    """

    # Temperatures (°F)
    ambient_temp_f: float = 70.0
    inlet_water_temp_f: float = 65.0
    refrigerant_temp_f: float = -20.0  # Evaporator temperature
    hot_gas_temp_f: float = 140.0  # Hot gas bypass temperature
    freezing_point_f: float = 32.0  # Water freezing point

    # Heat transfer coefficients (W/m²·K)
    # Tuned for realistic cycle times with 0.5kg plate
    #
    # Refrigerant evaporator to plate - main cooling
    # Real evaporators: 1000-5000 W/(m²·K), but small contact area
    h_refrigerant: float = 350.0
    # Hot gas to plate - heating during harvest
    h_hotgas: float = 80.0
    # Forced convection of water over plate (no ice)
    # Water flowing over cold plate with recirculation pump
    # Higher value for turbulent flow: 500-2000 W/(m²·K)
    h_water_plate: float = 800.0
    # Natural convection - reservoir to ambient air
    h_ambient_water: float = 5.0
    # Natural convection - plate to ambient air
    h_ambient_plate: float = 8.0

    # Ice thermal properties
    # Ice thermal conductivity: ~2.2 W/(m·K)
    # As ice builds, effective h decreases: h_eff = k_ice / thickness
    ice_thermal_conductivity: float = 2.2  # W/(m·K)
    max_ice_thickness_m: float = 0.015  # 15mm max ice thickness
    # Latent heat of fusion for ice: 334 kJ/kg = 334000 J/kg
    ice_latent_heat: float = 334000.0  # J/kg

    # Surface areas (m²)
    # Ice makers have large plate surface for water contact
    plate_water_contact_area: float = 0.08  # ~40cm x 20cm (larger for better heat transfer)
    evaporator_area: float = 0.02  # Refrigerant contact area
    reservoir_surface_area: float = 0.04  # Exposed water surface
    plate_ambient_area: float = 0.03  # Plate exposed to air

    # Flow rates
    water_inlet_flow_rate: float = 0.05  # L/s when valve open

    # Reservoir parameters
    reservoir_volume_liters: float = 1.0
    reservoir_max_volume_liters: float = 1.5

    # Plate parameters - lighter plate responds faster
    plate_mass_kg: float = 0.5  # Aluminum plate mass

    # Speed multiplier for accelerated simulation
    speed_multiplier: float = 1.0


@dataclass
class Reservoir:
    """Water reservoir with thermal properties.

    Models a water reservoir that can receive inlet water, lose water to
    overflow, and exchange heat with the cooling plate and ambient air.
    """

    volume_liters: float = 1.0
    temp_f: float = 70.0
    max_volume_liters: float = 1.5

    # Physical constants
    WATER_DENSITY: float = 1.0  # kg/L
    WATER_SPECIFIC_HEAT: float = 4186.0  # J/(kg·K)

    @property
    def mass_kg(self) -> float:
        """Current water mass in kg."""
        return self.volume_liters * self.WATER_DENSITY

    @property
    def thermal_mass(self) -> float:
        """Thermal mass in J/K - energy needed to change temp by 1 Kelvin."""
        return self.mass_kg * self.WATER_SPECIFIC_HEAT

    @property
    def temp_k(self) -> float:
        """Temperature in Kelvin."""
        return fahrenheit_to_kelvin(self.temp_f)

    def add_water(self, volume_liters: float, temp_f: float) -> float:
        """Mix incoming water with existing reservoir.

        Uses conservation of energy for mixing:
        T_final = (m1*c*T1 + m2*c*T2) / (m1*c + m2*c)
                = (V1*T1 + V2*T2) / (V1 + V2)  (since density and c are same)

        Args:
            volume_liters: Volume of water to add
            temp_f: Temperature of incoming water in Fahrenheit

        Returns:
            Volume that overflowed (if any)
        """
        if volume_liters <= 0:
            return 0.0

        # Calculate mixed temperature
        total_volume = self.volume_liters + volume_liters
        self.temp_f = (
            self.volume_liters * self.temp_f + volume_liters * temp_f
        ) / total_volume

        # Handle overflow
        overflow = max(0.0, total_volume - self.max_volume_liters)
        self.volume_liters = min(total_volume, self.max_volume_liters)

        return overflow

    def apply_heat_transfer(self, heat_joules: float) -> None:
        """Apply heat transfer to the reservoir.

        Args:
            heat_joules: Heat energy in Joules (positive = heating, negative = cooling)
        """
        if self.thermal_mass <= 0:
            return

        # ΔT(K) = Q / (m * c)
        delta_k = heat_joules / self.thermal_mass
        # Convert to Fahrenheit change: ΔT(F) = ΔT(K) * 9/5
        self.temp_f += delta_k * 9 / 5


@dataclass
class CoolingPlate:
    """Aluminum cooling plate with thermal properties.

    Models the ice-making plate that is cooled by refrigerant,
    heated by hot gas, and exchanges heat with water.
    """

    mass_kg: float = 2.0
    temp_f: float = 70.0

    # Physical constants for aluminum
    ALUMINUM_SPECIFIC_HEAT: float = 897.0  # J/(kg·K)

    @property
    def thermal_mass(self) -> float:
        """Thermal mass in J/K - energy needed to change temp by 1 Kelvin."""
        return self.mass_kg * self.ALUMINUM_SPECIFIC_HEAT

    @property
    def temp_k(self) -> float:
        """Temperature in Kelvin."""
        return fahrenheit_to_kelvin(self.temp_f)

    def apply_heat_transfer(self, heat_joules: float) -> None:
        """Apply heat transfer to the plate.

        Args:
            heat_joules: Heat energy in Joules (positive = heating, negative = cooling)
        """
        if self.thermal_mass <= 0:
            return

        # ΔT(K) = Q / (m * c)
        delta_k = heat_joules / self.thermal_mass
        # Convert to Fahrenheit change: ΔT(F) = ΔT(K) * 9/5
        self.temp_f += delta_k * 9 / 5


@dataclass
class IceBin:
    """Ice storage bin with thermal properties.

    Models ice accumulating in the bin from harvest cycles.
    The bin sensor temperature depends on ice level - when full,
    ice contacts the sensor and reads cold (~32°F). When empty,
    the sensor reads ambient temperature.

    Ice melts over time due to ambient heat, reducing the ice level.
    """

    ice_mass_kg: float = 0.0  # Total ice mass in bin
    temp_f: float = 70.0  # Bin/sensor temperature

    # Bin capacity - about 10 harvest cycles worth of ice
    # Each cycle produces ~1kg of ice (0.08m² × 0.015m × 917 kg/m³ ≈ 1.1 kg)
    max_ice_mass_kg: float = 10.0  # ~10 cycles to fill

    # Physical constants
    ICE_SPECIFIC_HEAT: float = 2090.0  # J/(kg·K) - ice specific heat
    ICE_LATENT_HEAT: float = 334000.0  # J/kg - latent heat of fusion
    ICE_DENSITY: float = 917.0  # kg/m³

    # Bin thermal properties
    BIN_SURFACE_AREA: float = 0.2  # m² - exposed surface for heat transfer
    H_AMBIENT: float = 5.0  # W/(m²·K) - natural convection

    @property
    def fill_fraction(self) -> float:
        """Fraction of bin capacity filled (0.0 to 1.0)."""
        return min(1.0, self.ice_mass_kg / self.max_ice_mass_kg)

    @property
    def is_full(self) -> bool:
        """True if bin is at or above capacity."""
        return self.ice_mass_kg >= self.max_ice_mass_kg

    def add_ice(self, mass_kg: float) -> None:
        """Add harvested ice to the bin.

        Args:
            mass_kg: Mass of ice to add in kg
        """
        self.ice_mass_kg = min(self.max_ice_mass_kg, self.ice_mass_kg + mass_kg)
        logger.debug("Bin ice: added %.3f kg, total %.3f kg (%.0f%% full)",
                     mass_kg, self.ice_mass_kg, self.fill_fraction * 100)

    def melt_ice(self, energy_joules: float) -> float:
        """Melt ice in the bin due to heat input.

        Args:
            energy_joules: Heat energy absorbed by ice

        Returns:
            Mass of ice melted in kg
        """
        if self.ice_mass_kg <= 0 or energy_joules <= 0:
            return 0.0

        # Mass that can be melted: m = Q / L
        max_melt = energy_joules / self.ICE_LATENT_HEAT
        actual_melt = min(max_melt, self.ice_mass_kg)
        self.ice_mass_kg -= actual_melt

        return actual_melt

    def update_temperature(self, ambient_temp_f: float) -> None:
        """Update bin sensor temperature based on ice level.

        The sensor is mounted at a specific height in the bin. Once ice
        accumulates high enough to contact the sensor, the temperature
        drops rapidly to near freezing. Below that level, the sensor
        reads ambient air temperature.

        Model: sensor contact threshold at ~70% fill
        - Below 70%: sensor reads ambient (no ice contact)
        - At/above 70%: ice contacts sensor, temp drops to ~32°F
        """
        freezing = 32.0
        fill = self.fill_fraction

        # Sensor contact threshold - ice touches sensor around 70% fill
        contact_threshold = 0.7

        if fill < contact_threshold:
            # Ice hasn't reached the sensor yet - reads ambient
            self.temp_f = ambient_temp_f
        else:
            # Ice is touching the sensor - temperature drops to freezing
            # Small variation based on how much ice is pressing against sensor
            self.temp_f = freezing


class PhysicsSimulator:
    """Physics-based thermal simulator for icemaker.

    Simulates realistic thermal behavior using:
    - Heat transfer equation: Q = h * A * ΔT * dt
    - Energy conservation for water mixing
    - Ice formation with latent heat of fusion
    - Discrete thermal bodies (Reservoir, CoolingPlate)

    Ice formation model:
    - Once water reaches 32°F, ice starts forming on the cold plate
    - Heat extracted from water goes into latent heat (phase change)
    - Water stays at ~32°F while ice is forming
    - Ice thickness builds, insulating plate from water
    - Plate continues to cool; plate temp indicates ice thickness

    The simulator interfaces with the FSM through the same HAL interface
    as real hardware (MockGPIO callback, MockSensors provider).
    """

    def __init__(self, params: Optional[SimulatorParams] = None) -> None:
        self.params = params or SimulatorParams()

        # Create thermal bodies
        self.reservoir = Reservoir(
            volume_liters=self.params.reservoir_volume_liters,
            temp_f=self.params.ambient_temp_f,
            max_volume_liters=self.params.reservoir_max_volume_liters,
        )
        self.plate = CoolingPlate(
            mass_kg=self.params.plate_mass_kg,
            temp_f=self.params.ambient_temp_f,
        )
        self.ice_bin = IceBin(
            ice_mass_kg=0.0,
            temp_f=self.params.ambient_temp_f,
        )

        # Relay states (updated via callback from MockGPIO)
        self._relay_states: dict[RelayName, bool] = {r: False for r in RelayName}

        # Ice formation tracking (on plate)
        self.ice_thickness_m: float = 0.0  # Current ice layer thickness in meters
        self.ice_mass_kg: float = 0.0  # Total ice mass formed on plate

        # Track previous state for detecting harvest completion
        self._prev_hot_gas_on: bool = False

        # Simulation state
        self.simulated_time_seconds: float = 0.0
        self._accumulated_time: float = 0.0  # Partial tick accumulator
        self._running = False
        self._update_task: Optional[asyncio.Task[None]] = None

    # -------------------------------------------------------------------------
    # HAL Interface Methods (called by MockGPIO/MockSensors)
    # -------------------------------------------------------------------------

    def set_relay_state(self, relay: RelayName, on: bool) -> None:
        """Set relay state - called by MockGPIO callback."""
        self._relay_states[relay] = on

    def get_temperature(self, sensor: SensorName) -> float:
        """Get temperature - called by MockSensors provider."""
        if sensor == SensorName.PLATE:
            return self.plate.temp_f
        elif sensor == SensorName.ICE_BIN:
            return self.ice_bin.temp_f
        # Unknown sensor - return ambient
        return self.params.ambient_temp_f

    def get_water_temp(self) -> float:
        """Get reservoir water temperature."""
        return self.reservoir.temp_f

    def get_simulated_time(self) -> float:
        """Get elapsed simulated time in seconds."""
        return self.simulated_time_seconds

    def set_speed_multiplier(self, multiplier: float) -> None:
        """Set simulation speed multiplier."""
        multiplier = max(0.1, min(1000.0, multiplier))
        self.params.speed_multiplier = multiplier
        logger.info("Simulation speed set to %.1fx", multiplier)

    def get_speed_multiplier(self) -> float:
        """Get current simulation speed multiplier."""
        return self.params.speed_multiplier

    # -------------------------------------------------------------------------
    # Relay State Helpers
    # -------------------------------------------------------------------------

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

    # -------------------------------------------------------------------------
    # Ice Layer Properties
    # -------------------------------------------------------------------------

    def _get_effective_h_through_ice(self) -> float:
        """Get effective heat transfer coefficient through ice layer.

        As ice builds on the plate, it insulates the plate from the water.
        The effective h decreases based on ice thickness:
            h_eff = k_ice / thickness (for conduction through ice)

        With no ice, water contacts plate directly at h_water_plate.
        With ice, heat must conduct through ice layer first.

        For thin ice, use series resistance model:
            1/h_total = 1/h_water + thickness/k_ice
        """
        p = self.params

        if self.ice_thickness_m <= 0:
            return p.h_water_plate

        # Series thermal resistance: water convection + ice conduction
        # R_total = R_water + R_ice = 1/h_water + thickness/k_ice
        r_water = 1.0 / p.h_water_plate
        r_ice = self.ice_thickness_m / p.ice_thermal_conductivity

        # h_effective = 1 / R_total
        h_effective = 1.0 / (r_water + r_ice)

        return h_effective

    def get_ice_thickness_mm(self) -> float:
        """Get ice thickness in millimeters for display."""
        return self.ice_thickness_m * 1000.0

    def get_bin_fill_percent(self) -> float:
        """Get bin fill level as percentage (0-100)."""
        return self.ice_bin.fill_fraction * 100.0

    def get_bin_ice_mass_kg(self) -> float:
        """Get total ice mass in bin (kg)."""
        return self.ice_bin.ice_mass_kg

    # -------------------------------------------------------------------------
    # Physics Calculations
    # -------------------------------------------------------------------------

    def _calculate_heat_transfer(
        self,
        h: float,
        area: float,
        t1_f: float,
        t2_f: float,
        dt: float,
    ) -> float:
        """Calculate heat transfer between two bodies.

        Q = h * A * (T1 - T2) * dt

        Args:
            h: Heat transfer coefficient (W/m²·K)
            area: Contact area (m²)
            t1_f: Temperature of body 1 in Fahrenheit
            t2_f: Temperature of body 2 in Fahrenheit
            dt: Time step in seconds

        Returns:
            Heat transferred in Joules (positive = heat flows from T1 to T2)
        """
        # Convert temperature difference to Kelvin
        # ΔT(K) = ΔT(F) * 5/9
        delta_t_k = (t1_f - t2_f) * 5 / 9

        # Q = h * A * ΔT * dt (in Joules, since h is in W/m²·K)
        return h * area * delta_t_k * dt

    def _update_physics(self, dt: float) -> None:
        """Update physics for one time step.

        Args:
            dt: Time step in seconds (already scaled by speed_multiplier)
        """
        p = self.params

        compressor_on = self._is_compressor_on()
        hot_gas_on = self._is_hot_gas_on()
        pump_on = self._is_pump_on()
        water_valve_on = self._is_water_valve_on()

        # ---------------------------------------------------------------------
        # 1. Water Inlet (valve open)
        # ---------------------------------------------------------------------
        if water_valve_on:
            volume_added = p.water_inlet_flow_rate * dt
            self.reservoir.add_water(volume_added, p.inlet_water_temp_f)

        # ---------------------------------------------------------------------
        # 2. Heat transfer between plate and water (pump on)
        # ---------------------------------------------------------------------
        if pump_on:
            # Physical constants for ice
            ice_density = 917.0  # kg/m³
            k_ice = p.ice_thermal_conductivity  # 2.2 W/(m·K)

            # Check conditions for ice formation
            plate_below_freezing = self.plate.temp_f < p.freezing_point_f
            water_can_freeze = self.reservoir.temp_f <= p.freezing_point_f + 0.5

            if plate_below_freezing and water_can_freeze and compressor_on:
                # =============================================================
                # ICE FORMATION MODE
                # =============================================================
                # Ice grows on the plate surface. Heat flows:
                #   water (32°F) -> ice layer -> plate (cold)
                #
                # The rate of ice growth is limited by heat conduction through
                # the existing ice layer. Stefan problem for ice growth:
                #   dh/dt = k_ice * (T_freeze - T_plate) / (ρ * L * h)
                #
                # For thin ice, we use a minimum thickness to avoid division
                # by zero and to represent initial nucleation.
                # =============================================================

                # Temperature difference drives ice formation (in Kelvin)
                # Plate is below freezing, so (T_freeze - T_plate) is positive
                delta_t_k = (p.freezing_point_f - self.plate.temp_f) * 5 / 9

                # Use minimum thickness for initial ice formation (nucleation)
                # This represents ~0.1mm initial ice crystal layer
                min_ice_thickness = 0.0001  # 0.1mm in meters
                effective_thickness = max(self.ice_thickness_m, min_ice_thickness)

                # Heat flux through ice layer: q = k * A * dT / thickness
                # This is conduction through the ice (W)
                q_through_ice = (
                    k_ice * p.plate_water_contact_area * delta_t_k / effective_thickness
                )

                # Energy transferred this timestep (Joules)
                energy_for_freezing = q_through_ice * dt

                # Mass of ice formed: m = Q / L
                ice_formed_kg = energy_for_freezing / p.ice_latent_heat
                self.ice_mass_kg += ice_formed_kg

                # Update ice thickness from total mass
                self.ice_thickness_m = self.ice_mass_kg / (
                    ice_density * p.plate_water_contact_area
                )

                # Clamp to max thickness
                if self.ice_thickness_m > p.max_ice_thickness_m:
                    self.ice_thickness_m = p.max_ice_thickness_m
                    self.ice_mass_kg = (
                        self.ice_thickness_m * ice_density * p.plate_water_contact_area
                    )

                # Water releases latent heat but stays at freezing point
                # (phase change absorbs energy without temperature change)
                if self.reservoir.temp_f > p.freezing_point_f:
                    # Cool water down to freezing point
                    q_to_freezing = self._calculate_heat_transfer(
                        h=p.h_water_plate,
                        area=p.plate_water_contact_area,
                        t1_f=self.reservoir.temp_f,
                        t2_f=p.freezing_point_f,
                        dt=dt,
                    )
                    self.reservoir.apply_heat_transfer(-q_to_freezing)
                    if self.reservoir.temp_f < p.freezing_point_f:
                        self.reservoir.temp_f = p.freezing_point_f

                # Plate receives heat conducted through ice from the freezing interface
                # This warms the plate slightly, counteracting refrigerant cooling
                self.plate.apply_heat_transfer(energy_for_freezing)

            else:
                # =============================================================
                # NORMAL HEAT TRANSFER (no ice formation)
                # =============================================================
                # Direct heat exchange between water and plate (possibly through
                # existing ice layer which adds thermal resistance)

                h_effective = self._get_effective_h_through_ice()

                q_water_plate = self._calculate_heat_transfer(
                    h=h_effective,
                    area=p.plate_water_contact_area,
                    t1_f=self.reservoir.temp_f,
                    t2_f=self.plate.temp_f,
                    dt=dt,
                )

                # Heat flows from warmer to cooler
                self.reservoir.apply_heat_transfer(-q_water_plate)
                self.plate.apply_heat_transfer(+q_water_plate)

        # ---------------------------------------------------------------------
        # 3. Refrigerant cooling (compressor on, no hot gas)
        # ---------------------------------------------------------------------
        if compressor_on and not hot_gas_on:
            # Plate is cooled by refrigerant evaporator
            q_refrigerant = self._calculate_heat_transfer(
                h=p.h_refrigerant,
                area=p.evaporator_area,
                t1_f=self.plate.temp_f,
                t2_f=p.refrigerant_temp_f,
                dt=dt,
            )
            # Positive Q means plate is warmer than refrigerant, plate loses heat
            self.plate.apply_heat_transfer(-q_refrigerant)

        # ---------------------------------------------------------------------
        # 4. Hot gas heating (compressor on + hot gas solenoid)
        # ---------------------------------------------------------------------
        if compressor_on and hot_gas_on:
            # Plate is heated by hot gas bypass
            q_hotgas = self._calculate_heat_transfer(
                h=p.h_hotgas,
                area=p.evaporator_area,
                t1_f=p.hot_gas_temp_f,
                t2_f=self.plate.temp_f,
                dt=dt,
            )

            # During harvest, ice melts as plate heats
            # Heat goes into melting ice (latent heat) until plate reaches 32°F
            # Ice melts from the plate side first (where heat is applied)
            if self.ice_mass_kg > 0:
                ice_density = 917.0

                # While there's ice and plate is below/at freezing, energy goes to melting
                # The plate-ice interface must reach 32°F for ice to release
                if self.plate.temp_f <= p.freezing_point_f + 2.0:
                    # Energy available for melting (Joules)
                    energy_for_melting = q_hotgas * dt if q_hotgas > 0 else 0

                    # Mass of ice that can be melted: m = Q / L
                    ice_melted_kg = energy_for_melting / p.ice_latent_heat
                    self.ice_mass_kg = max(0.0, self.ice_mass_kg - ice_melted_kg)

                    # Update thickness
                    if self.ice_mass_kg > 0:
                        self.ice_thickness_m = self.ice_mass_kg / (
                            ice_density * p.plate_water_contact_area
                        )
                    else:
                        self.ice_thickness_m = 0.0

                    # Plate temperature held near freezing while ice melts
                    # (latent heat absorbs energy without temp change)
                    # Only a fraction of heat goes to raising plate temp
                    self.plate.apply_heat_transfer(q_hotgas * 0.3)
                else:
                    # Plate above freezing, normal heating
                    self.plate.apply_heat_transfer(+q_hotgas)
            else:
                # No ice, normal heating
                self.plate.apply_heat_transfer(+q_hotgas)

        # ---------------------------------------------------------------------
        # 5. Ice harvest completion - transfer ice to bin
        # ---------------------------------------------------------------------
        # When hot gas turns off after being on (harvest ends), ice drops into bin
        if self._prev_hot_gas_on and not hot_gas_on:
            # Harvest just completed - transfer plate ice to bin
            if self.ice_mass_kg > 0:
                logger.info(
                    "Harvest complete: %.3f kg ice transferred to bin (bin now %.1f%% full)",
                    self.ice_mass_kg,
                    (self.ice_bin.ice_mass_kg + self.ice_mass_kg)
                    / self.ice_bin.max_ice_mass_kg
                    * 100,
                )
                self.ice_bin.add_ice(self.ice_mass_kg)
                self.ice_mass_kg = 0.0
                self.ice_thickness_m = 0.0

        self._prev_hot_gas_on = hot_gas_on

        # ---------------------------------------------------------------------
        # 6. Ice bin melting from ambient heat
        # ---------------------------------------------------------------------
        if self.ice_bin.ice_mass_kg > 0:
            # Heat transfer from ambient air to ice bin
            q_bin_ambient = self._calculate_heat_transfer(
                h=self.ice_bin.H_AMBIENT,
                area=self.ice_bin.BIN_SURFACE_AREA,
                t1_f=p.ambient_temp_f,
                t2_f=32.0,  # Ice surface at freezing point
                dt=dt,
            )
            if q_bin_ambient > 0:
                self.ice_bin.melt_ice(q_bin_ambient)

        # Update bin sensor temperature based on ice level
        self.ice_bin.update_temperature(p.ambient_temp_f)

        # ---------------------------------------------------------------------
        # 7. Ambient heat loss/gain
        # ---------------------------------------------------------------------
        # Reservoir drifts toward ambient
        q_reservoir_ambient = self._calculate_heat_transfer(
            h=p.h_ambient_water,
            area=p.reservoir_surface_area,
            t1_f=p.ambient_temp_f,
            t2_f=self.reservoir.temp_f,
            dt=dt,
        )
        self.reservoir.apply_heat_transfer(+q_reservoir_ambient)

        # Plate drifts toward ambient (when not actively cooled/heated)
        if not compressor_on:
            q_plate_ambient = self._calculate_heat_transfer(
                h=p.h_ambient_plate,
                area=p.plate_ambient_area,
                t1_f=p.ambient_temp_f,
                t2_f=self.plate.temp_f,
                dt=dt,
            )
            self.plate.apply_heat_transfer(+q_plate_ambient)

    def tick(self) -> None:
        """Advance simulation by one fixed tick.

        Each tick advances simulated time by TICK_SIZE_SECONDS.
        This ensures deterministic behavior regardless of speed multiplier.
        """
        self._update_physics(TICK_SIZE_SECONDS)
        self.simulated_time_seconds += TICK_SIZE_SECONDS

    def update(self, dt: float) -> None:
        """Update simulation for a wall-clock time step.

        Converts wall-clock time to simulation ticks based on speed multiplier.
        Uses fixed tick sizes for deterministic behavior.

        Args:
            dt: Wall-clock time step in seconds
        """
        # Cap wall-clock dt to prevent huge jumps after delays/pauses
        # Maximum 500ms wall-clock between updates (any larger suggests system pause)
        dt = min(dt, 0.5)

        # Calculate how many simulated seconds should pass
        simulated_dt = dt * self.params.speed_multiplier

        # Accumulate partial ticks
        self._accumulated_time += simulated_dt

        # Run whole ticks, but cap to prevent runaway physics
        ticks_this_update = 0
        while self._accumulated_time >= TICK_SIZE_SECONDS and ticks_this_update < MAX_TICKS_PER_UPDATE:
            self.tick()
            self._accumulated_time -= TICK_SIZE_SECONDS
            ticks_this_update += 1

        # If we hit the cap, discard excess accumulated time to prevent buildup
        if ticks_this_update >= MAX_TICKS_PER_UPDATE and self._accumulated_time > TICK_SIZE_SECONDS:
            logger.warning(
                "Physics tick cap reached: discarding %.1fs of accumulated time",
                self._accumulated_time,
            )
            self._accumulated_time = self._accumulated_time % TICK_SIZE_SECONDS

    # -------------------------------------------------------------------------
    # Background Task (continuous simulation)
    # -------------------------------------------------------------------------

    async def run(self, update_interval: float = 0.05) -> None:
        """Run continuous simulation loop.

        Args:
            update_interval: Wall-clock seconds between updates (default 50ms)
        """
        self._running = True
        logger.info(
            "Physics simulation started (speed: %.1fx)", self.params.speed_multiplier
        )

        last_log_time = 0.0
        log_interval = 10.0  # Log every 10 simulated seconds

        while self._running:
            # Use fixed update_interval for deterministic behavior
            # rather than measuring actual elapsed time which varies with system load
            self.update(update_interval)

            # Periodic logging
            if self.simulated_time_seconds - last_log_time >= log_interval:
                last_log_time = self.simulated_time_seconds
                self._log_state()

            try:
                await asyncio.sleep(update_interval)
            except asyncio.CancelledError:
                break

        logger.info("Physics simulation stopped")

    async def start(self, update_interval: float = 0.05) -> None:
        """Start simulation as background task."""
        if self._update_task is not None:
            return
        self._update_task = asyncio.create_task(self.run(update_interval))

    async def stop(self) -> None:
        """Stop the simulation."""
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
        water_temp: float = 70.0,
        water_volume: float = 1.0,
        bin_ice_mass: float = 0.0,
    ) -> None:
        """Reset simulation to initial state.

        Args:
            plate_temp: Initial plate temperature in °F
            water_temp: Initial water reservoir temperature in °F
            water_volume: Initial water volume in liters
            bin_ice_mass: Initial ice mass in bin (kg), 0 for empty
        """
        self.plate.temp_f = plate_temp
        self.reservoir.temp_f = water_temp
        self.reservoir.volume_liters = water_volume
        self.ice_thickness_m = 0.0
        self.ice_mass_kg = 0.0
        self.ice_bin.ice_mass_kg = bin_ice_mass
        self.ice_bin.update_temperature(self.params.ambient_temp_f)
        self._prev_hot_gas_on = False
        self.simulated_time_seconds = 0.0
        self._accumulated_time = 0.0
        for relay in RelayName:
            self._relay_states[relay] = False
        logger.info(
            "Simulation reset: plate=%.1f°F, water=%.1f°F, volume=%.2fL, bin=%.1f%% full",
            plate_temp,
            water_temp,
            water_volume,
            self.ice_bin.fill_fraction * 100,
        )

    def _log_state(self) -> None:
        """Log current simulation state."""
        relays = self._relay_states
        active_relays = [r.value for r, on in relays.items() if on]
        relay_str = ", ".join(active_relays) if active_relays else "none"

        comp_on = self._is_compressor_on()
        hot_gas = self._is_hot_gas_on()
        pump_on = self._is_pump_on()

        if hot_gas and comp_on:
            mode = "HEATING"
        elif comp_on and pump_on:
            mode = "ICE_MAKING"
        elif comp_on:
            mode = "COOLING"
        else:
            mode = "IDLE"

        ice_mm = self.get_ice_thickness_mm()
        bin_pct = self.get_bin_fill_percent()
        logger.debug(
            "SIM t=%.1fs | mode=%s | plate=%.1f°F water=%.1f°F | ice=%.1fmm | bin=%.0f%% | relays=[%s]",
            self.simulated_time_seconds,
            mode,
            self.plate.temp_f,
            self.reservoir.temp_f,
            ice_mm,
            bin_pct,
            relay_str,
        )
