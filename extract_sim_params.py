#!/usr/bin/env python3
"""Extract simulation parameters from real icemaker data.

This script analyzes actual ice machine temperature logs to calculate
the heat transfer coefficients and other parameters needed to accurately
model the system dynamics in simulation.

Physics background:
- The plate temperature follows Newton's law of cooling/heating:
  dT/dt = h * A * (T_source - T_plate) / (m * c)

- For a first-order thermal system:
  T(t) = T_eq + (T_0 - T_eq) * exp(-t/τ)
  where τ = m * c / (h * A) is the thermal time constant

- By fitting exponential curves to cooling/heating data, we can extract
  the effective h*A product, and thus the heat transfer coefficients.
"""

import csv
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
from scipy.optimize import curve_fit


@dataclass
class DataPoint:
    """Single data point from the icemaker log."""
    timestamp: datetime
    state: str
    plate_temp_f: float
    bin_temp_f: float
    target_temp_f: float
    cycle_count: int
    chill_mode: str
    compressor_1: bool
    compressor_2: bool
    condenser_fan: bool
    hot_gas_solenoid: bool
    water_valve: bool
    recirculating_pump: bool
    ice_cutter: bool


def parse_csv(filepath: str) -> list[DataPoint]:
    """Parse the icemaker CSV log file."""
    data_points = []

    with open(filepath, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                dp = DataPoint(
                    timestamp=datetime.fromisoformat(row['timestamp'].replace('Z', '+00:00')),
                    state=row['state'],
                    plate_temp_f=float(row['plate_temp_f']),
                    bin_temp_f=float(row['bin_temp_f']),
                    target_temp_f=float(row['target_temp_f']),
                    cycle_count=int(row['cycle_count']),
                    chill_mode=row['chill_mode'],
                    compressor_1=row['compressor_1'] == '1',
                    compressor_2=row['compressor_2'] == '1',
                    condenser_fan=row['condenser_fan'] == '1',
                    hot_gas_solenoid=row['hot_gas_solenoid'] == '1',
                    water_valve=row['water_valve'] == '1',
                    recirculating_pump=row['recirculating_pump'] == '1',
                    ice_cutter=row['ice_cutter'] == '1',
                )
                data_points.append(dp)
            except (ValueError, KeyError) as e:
                continue  # Skip header or malformed rows

    return data_points


def deduplicate_by_temperature(data: list[DataPoint]) -> list[DataPoint]:
    """Remove consecutive points with the same temperature.

    The log has many duplicate readings - keep only points where
    temperature actually changes to get cleaner data for fitting.
    """
    if not data:
        return []

    result = [data[0]]
    for dp in data[1:]:
        if dp.plate_temp_f != result[-1].plate_temp_f:
            result.append(dp)
    return result


def exponential_decay(t: np.ndarray, T_eq: float, T_0: float, tau: float) -> np.ndarray:
    """Exponential temperature decay/rise model.

    T(t) = T_eq + (T_0 - T_eq) * exp(-t/tau)
    """
    return T_eq + (T_0 - T_eq) * np.exp(-t / tau)


def fit_exponential(times: np.ndarray, temps: np.ndarray,
                   cooling: bool = True) -> tuple[float, float, float]:
    """Fit exponential model to temperature data.

    Returns (T_equilibrium, T_initial, time_constant_seconds)
    """
    # Normalize time to start at 0
    t = times - times[0]

    # Initial guesses
    T_0_guess = temps[0]
    T_eq_guess = temps[-1] if cooling else temps[-1]
    tau_guess = (t[-1] - t[0]) / 3  # Rough guess: 3 time constants to mostly complete

    try:
        # Bounds to help convergence
        if cooling:
            # Cooling: T_eq < T_0
            bounds = (
                [-100, temps.min() - 10, 1],  # Lower bounds
                [temps.max() + 10, 200, 10000]  # Upper bounds
            )
        else:
            # Heating: T_eq > T_0
            bounds = (
                [temps.min() - 10, -100, 1],
                [200, temps.max() + 10, 10000]
            )

        popt, pcov = curve_fit(
            exponential_decay, t, temps,
            p0=[T_eq_guess, T_0_guess, tau_guess],
            bounds=bounds,
            maxfev=5000
        )
        return popt[0], popt[1], popt[2]
    except Exception as e:
        print(f"  Warning: Curve fit failed: {e}")
        return T_eq_guess, T_0_guess, tau_guess


def extract_cooling_segments(data: list[DataPoint]) -> list[list[DataPoint]]:
    """Extract segments where compressor is on and hot gas is off (cooling)."""
    segments = []
    current_segment = []

    for dp in data:
        is_cooling = (dp.compressor_1 or dp.compressor_2) and not dp.hot_gas_solenoid

        if is_cooling:
            current_segment.append(dp)
        else:
            if len(current_segment) > 10:  # Minimum segment length
                segments.append(current_segment)
            current_segment = []

    if len(current_segment) > 10:
        segments.append(current_segment)

    return segments


def extract_prechill_segments(data: list[DataPoint]) -> list[list[DataPoint]]:
    """Extract prechill segments (cooling without pump, above freezing).

    Prechill is the most useful for determining h_refrigerant because:
    - No latent heat effects (no ice formation)
    - Pure sensible heat transfer
    - Plate temperature well above freezing
    """
    segments = []
    current_segment = []

    for dp in data:
        is_prechill = (
            (dp.compressor_1 or dp.compressor_2)
            and not dp.hot_gas_solenoid
            and not dp.recirculating_pump  # Pump off during prechill
            and dp.plate_temp_f > 32.0  # Above freezing
        )

        if is_prechill:
            current_segment.append(dp)
        else:
            if len(current_segment) > 5:
                segments.append(current_segment)
            current_segment = []

    if len(current_segment) > 5:
        segments.append(current_segment)

    return segments


def extract_ice_making_segments(data: list[DataPoint]) -> list[list[DataPoint]]:
    """Extract ice-making segments (cooling with pump, near/below freezing).

    During ice making, latent heat of fusion dominates, so the apparent
    time constant is much longer than pure sensible heat transfer.
    """
    segments = []
    current_segment = []

    for dp in data:
        is_ice_making = (
            (dp.compressor_1 or dp.compressor_2)
            and not dp.hot_gas_solenoid
            and dp.recirculating_pump  # Pump on
            and dp.plate_temp_f < 35.0  # Near or below freezing
        )

        if is_ice_making:
            current_segment.append(dp)
        else:
            if len(current_segment) > 10:
                segments.append(current_segment)
            current_segment = []

    if len(current_segment) > 10:
        segments.append(current_segment)

    return segments


def extract_heating_segments(data: list[DataPoint]) -> list[list[DataPoint]]:
    """Extract segments where hot gas solenoid is on (heating/harvest)."""
    segments = []
    current_segment = []

    for dp in data:
        is_heating = dp.hot_gas_solenoid and (dp.compressor_1 or dp.compressor_2)

        if is_heating:
            current_segment.append(dp)
        else:
            if len(current_segment) > 10:
                segments.append(current_segment)
            current_segment = []

    if len(current_segment) > 10:
        segments.append(current_segment)

    return segments


def analyze_segment(segment: list[DataPoint], segment_type: str) -> dict:
    """Analyze a temperature segment and extract parameters."""
    # Deduplicate to get actual temperature changes
    deduped = deduplicate_by_temperature(segment)

    if len(deduped) < 5:
        return None

    # Convert to numpy arrays
    base_time = deduped[0].timestamp.timestamp()
    times = np.array([dp.timestamp.timestamp() - base_time for dp in deduped])
    temps = np.array([dp.plate_temp_f for dp in deduped])

    # Fit exponential
    cooling = segment_type == "cooling"
    T_eq, T_0, tau = fit_exponential(times, temps, cooling=cooling)

    # Calculate temperature range and duration
    duration = times[-1] - times[0]
    temp_change = temps[-1] - temps[0]

    # Calculate instantaneous rates (dT/dt) for rate-based analysis
    if len(times) > 2:
        # Use central differences for better accuracy
        dt = np.diff(times)
        dT = np.diff(temps)
        rates = dT / dt  # °F/s
        # Filter out zero-duration intervals
        valid_rates = rates[dt > 0.1]  # Minimum 0.1s between points
        if len(valid_rates) > 0:
            avg_rate = np.mean(valid_rates)
            max_rate = np.max(np.abs(valid_rates))
        else:
            avg_rate = temp_change / duration if duration > 0 else 0
            max_rate = abs(avg_rate)
    else:
        avg_rate = temp_change / duration if duration > 0 else 0
        max_rate = abs(avg_rate)

    return {
        'type': segment_type,
        'duration_s': duration,
        'T_start_f': temps[0],
        'T_end_f': temps[-1],
        'T_change_f': temp_change,
        'T_equilibrium_f': T_eq,
        'time_constant_s': tau,
        'num_points': len(deduped),
        'avg_rate_f_per_s': avg_rate,
        'max_rate_f_per_s': max_rate,
    }


def calculate_h_A_from_rate(
    dT_dt: float,  # °F/s
    T_plate: float,  # °F
    T_source: float,  # °F
    mass_kg: float,
    specific_heat: float,  # J/(kg·K)
) -> float:
    """Calculate h*A from instantaneous rate of temperature change.

    From: dT/dt = h * A * (T_source - T_plate) / (m * c)
    Thus: h * A = m * c * dT/dt / (T_source - T_plate)

    Note: dT/dt in °F/s, but temperature difference also in °F,
    so they cancel and we just need to convert the thermal mass.

    Args:
        dT_dt: Rate of temperature change in °F/s
        T_plate: Plate temperature in °F
        T_source: Source temperature in °F (refrigerant or hot gas)
        mass_kg: Plate mass in kg
        specific_heat: Specific heat in J/(kg·K)

    Returns:
        h*A in W/K
    """
    delta_T = T_source - T_plate  # °F
    if abs(delta_T) < 1.0:
        return None  # Too small temperature difference

    # Convert dT/dt from °F/s to K/s: multiply by 5/9
    dT_dt_K = dT_dt * 5 / 9

    # h * A = m * c * (dT/dt in K/s) / (ΔT in K)
    # Since ΔT in K = ΔT in °F * 5/9, and dT/dt in K/s = dT/dt in °F/s * 5/9
    # the 5/9 factors cancel:
    # h * A = m * c * (dT/dt in °F/s) / (ΔT in °F)
    h_A = mass_kg * specific_heat * abs(dT_dt) / abs(delta_T)

    return h_A


def calculate_h_times_A(tau: float, mass_kg: float, specific_heat: float) -> float:
    """Calculate h*A from time constant.

    τ = m * c / (h * A)
    h * A = m * c / τ

    Args:
        tau: Time constant in seconds
        mass_kg: Mass in kg
        specific_heat: Specific heat in J/(kg·K)

    Returns:
        h*A in W/K
    """
    return mass_kg * specific_heat / tau


def main():
    if len(sys.argv) < 2:
        print("Usage: python extract_sim_params.py <csv_file>")
        print("Example: python extract_sim_params.py icemaker-log-2026-01-25-03-46-32.csv")
        sys.exit(1)

    csv_path = sys.argv[1]
    print(f"Analyzing: {csv_path}")
    print("=" * 70)

    # Parse data
    data = parse_csv(csv_path)
    print(f"Loaded {len(data)} data points")

    # Extract segments
    cooling_segments = extract_cooling_segments(data)
    heating_segments = extract_heating_segments(data)
    prechill_segments = extract_prechill_segments(data)
    ice_making_segments = extract_ice_making_segments(data)

    print(f"Found {len(cooling_segments)} total cooling segments")
    print(f"Found {len(prechill_segments)} prechill segments (cooling above freezing, no pump)")
    print(f"Found {len(ice_making_segments)} ice-making segments (cooling below freezing, pump on)")
    print(f"Found {len(heating_segments)} heating segments")
    print()

    # Physical constants
    ALUMINUM_SPECIFIC_HEAT = 897.0  # J/(kg·K)

    # Analyze prechill segments (most useful for h_refrigerant)
    print("=" * 70)
    print("PRECHILL ANALYSIS (Compressor ON, Pump OFF, Above Freezing)")
    print("This is the best data for calculating h_refrigerant (no latent heat effects)")
    print("=" * 70)

    prechill_results = []
    for i, seg in enumerate(prechill_segments):
        result = analyze_segment(seg, "cooling")
        if result and result['duration_s'] > 10:
            prechill_results.append(result)
            print(f"\nPrechill Segment {i+1}:")
            print(f"  Duration: {result['duration_s']:.1f}s")
            print(f"  Temperature: {result['T_start_f']:.1f}°F → {result['T_end_f']:.1f}°F (Δ={result['T_change_f']:.1f}°F)")
            print(f"  Average cooling rate: {result['avg_rate_f_per_s']:.3f}°F/s ({result['avg_rate_f_per_s']*60:.2f}°F/min)")
            print(f"  Equilibrium temp: {result['T_equilibrium_f']:.1f}°F")
            print(f"  Time constant τ: {result['time_constant_s']:.1f}s")

    # Analyze full cooling segments
    print("\n" + "=" * 70)
    print("FULL COOLING ANALYSIS (Compressor ON, Hot Gas OFF - includes ice making)")
    print("=" * 70)

    cooling_results = []
    for i, seg in enumerate(cooling_segments):
        result = analyze_segment(seg, "cooling")
        if result and result['duration_s'] > 30:  # Minimum 30s segment
            cooling_results.append(result)
            print(f"\nCooling Segment {i+1}:")
            print(f"  Duration: {result['duration_s']:.1f}s")
            print(f"  Temperature: {result['T_start_f']:.1f}°F → {result['T_end_f']:.1f}°F (Δ={result['T_change_f']:.1f}°F)")
            print(f"  Average cooling rate: {result['avg_rate_f_per_s']:.3f}°F/s ({result['avg_rate_f_per_s']*60:.2f}°F/min)")
            print(f"  Equilibrium temp: {result['T_equilibrium_f']:.1f}°F")
            print(f"  Time constant τ: {result['time_constant_s']:.1f}s")

    # Analyze heating segments
    print("\n" + "=" * 70)
    print("HEATING ANALYSIS (Hot Gas ON)")
    print("=" * 70)

    heating_results = []
    for i, seg in enumerate(heating_segments):
        result = analyze_segment(seg, "heating")
        if result and result['duration_s'] > 30:
            heating_results.append(result)
            print(f"\nHeating Segment {i+1}:")
            print(f"  Duration: {result['duration_s']:.1f}s")
            print(f"  Temperature: {result['T_start_f']:.1f}°F → {result['T_end_f']:.1f}°F (Δ={result['T_change_f']:.1f}°F)")
            print(f"  Average heating rate: {result['avg_rate_f_per_s']:.3f}°F/s ({result['avg_rate_f_per_s']*60:.2f}°F/min)")
            print(f"  Equilibrium temp: {result['T_equilibrium_f']:.1f}°F")
            print(f"  Time constant τ: {result['time_constant_s']:.1f}s")

    # Rate-based analysis
    print("\n" + "=" * 70)
    print("RATE-BASED PARAMETER ESTIMATION")
    print("=" * 70)

    # For rate-based analysis, we need to assume source temperatures
    # Typical refrigerant evaporator: -20°F to -30°F
    # Typical hot gas: 120°F to 160°F
    assumed_refrigerant_temp = -20.0  # °F
    assumed_hot_gas_temp = 140.0  # °F

    print(f"\nAssumed refrigerant temperature: {assumed_refrigerant_temp}°F")
    print(f"Assumed hot gas temperature: {assumed_hot_gas_temp}°F")

    # Calculate h*A from cooling rates
    if cooling_results:
        print("\nRate-based h*A estimation from cooling data:")
        for i, result in enumerate(cooling_results):
            avg_plate_temp = (result['T_start_f'] + result['T_end_f']) / 2
            for mass in [0.5, 1.0, 1.5]:
                h_A = calculate_h_A_from_rate(
                    dT_dt=result['avg_rate_f_per_s'],
                    T_plate=avg_plate_temp,
                    T_source=assumed_refrigerant_temp,
                    mass_kg=mass,
                    specific_heat=ALUMINUM_SPECIFIC_HEAT,
                )
                if h_A:
                    h = h_A / 0.02  # Assume 0.02 m² evaporator area
                    print(f"  Segment {i+1} (m={mass}kg): h*A = {h_A:.2f} W/K → h_refrigerant ≈ {h:.0f} W/(m²·K)")

    # Calculate h*A from heating rates
    if heating_results:
        print("\nRate-based h*A estimation from heating data:")
        for i, result in enumerate(heating_results):
            avg_plate_temp = (result['T_start_f'] + result['T_end_f']) / 2
            for mass in [0.5, 1.0, 1.5]:
                h_A = calculate_h_A_from_rate(
                    dT_dt=result['avg_rate_f_per_s'],
                    T_plate=avg_plate_temp,
                    T_source=assumed_hot_gas_temp,
                    mass_kg=mass,
                    specific_heat=ALUMINUM_SPECIFIC_HEAT,
                )
                if h_A:
                    h = h_A / 0.02  # Assume 0.02 m² evaporator area
                    print(f"  Segment {i+1} (m={mass}kg): h*A = {h_A:.2f} W/K → h_hotgas ≈ {h:.0f} W/(m²·K)")

    # Calculate recommended simulation parameters
    print("\n" + "=" * 70)
    print("TIME-CONSTANT-BASED PARAMETER ESTIMATION")
    print("=" * 70)

    # Prefer prechill data for h_refrigerant (pure sensible heat, no latent effects)
    if prechill_results:
        avg_cooling_tau = np.mean([r['time_constant_s'] for r in prechill_results])
        avg_cooling_T_eq = np.mean([r['T_equilibrium_f'] for r in prechill_results])
        print("\n(Using PRECHILL data for h_refrigerant - most accurate)")
    elif cooling_results:
        avg_cooling_tau = np.mean([r['time_constant_s'] for r in cooling_results])
        avg_cooling_T_eq = np.mean([r['T_equilibrium_f'] for r in cooling_results])
        print("\n(Using full cooling data - may be affected by latent heat)")
    else:
        avg_cooling_tau = 100.0  # Default
        avg_cooling_T_eq = -20.0
        print("\n(No cooling data found, using defaults)")

    if heating_results:
        avg_heating_tau = np.mean([r['time_constant_s'] for r in heating_results])
        avg_heating_T_eq = np.mean([r['T_equilibrium_f'] for r in heating_results])
    else:
        avg_heating_tau = 200.0  # Default
        avg_heating_T_eq = 140.0

    # Estimate plate mass from observed dynamics
    # We'll try different masses and see which gives reasonable h values
    print("\nParameter estimation for different plate masses:")
    print("-" * 70)

    for plate_mass in [0.3, 0.5, 0.75, 1.0, 1.5, 2.0]:
        h_A_cooling = calculate_h_times_A(avg_cooling_tau, plate_mass, ALUMINUM_SPECIFIC_HEAT)
        h_A_heating = calculate_h_times_A(avg_heating_tau, plate_mass, ALUMINUM_SPECIFIC_HEAT)

        # Assume evaporator area of ~0.02 m² (from current simulation)
        evaporator_area = 0.02
        h_refrigerant = h_A_cooling / evaporator_area
        h_hotgas = h_A_heating / evaporator_area

        print(f"\n  Plate mass = {plate_mass} kg:")
        print(f"    h*A (cooling) = {h_A_cooling:.2f} W/K")
        print(f"    h*A (heating) = {h_A_heating:.2f} W/K")
        print(f"    → h_refrigerant ≈ {h_refrigerant:.0f} W/(m²·K) (at A={evaporator_area} m²)")
        print(f"    → h_hotgas ≈ {h_hotgas:.0f} W/(m²·K) (at A={evaporator_area} m²)")

    # Generate SimulatorParams suggestion
    print("\n" + "=" * 70)
    print("SUGGESTED SimulatorParams UPDATE")
    print("=" * 70)

    # Use 0.5 kg as default plate mass (reasonable for small ice maker)
    recommended_mass = 0.5
    h_A_cooling = calculate_h_times_A(avg_cooling_tau, recommended_mass, ALUMINUM_SPECIFIC_HEAT)
    h_A_heating = calculate_h_times_A(avg_heating_tau, recommended_mass, ALUMINUM_SPECIFIC_HEAT)

    evaporator_area = 0.02
    h_refrigerant = h_A_cooling / evaporator_area
    h_hotgas = h_A_heating / evaporator_area

    # Use rate-based analysis which is more robust for short segments
    # Calculate average rates across all segments
    if cooling_results:
        avg_cooling_rate = np.mean([abs(r['avg_rate_f_per_s']) for r in cooling_results])
    else:
        avg_cooling_rate = 0.05  # Default

    if heating_results:
        avg_heating_rate = np.mean([abs(r['avg_rate_f_per_s']) for r in heating_results])
    else:
        avg_heating_rate = 0.4  # Default

    # Better estimates using rate-based analysis with reasonable assumptions
    # Assume -20°F refrigerant, 140°F hot gas, and calculate h*A
    assumed_refrigerant_temp = -20.0
    assumed_hot_gas_temp = 140.0
    recommended_mass = 1.0  # Start with 1kg as a reasonable ice maker plate
    evaporator_area = 0.02

    # Calculate h*A from average rates
    if cooling_results:
        avg_plate_temp_cooling = np.mean([(r['T_start_f'] + r['T_end_f'])/2 for r in cooling_results])
        h_A_cooling_rate = calculate_h_A_from_rate(
            dT_dt=-avg_cooling_rate,
            T_plate=avg_plate_temp_cooling,
            T_source=assumed_refrigerant_temp,
            mass_kg=recommended_mass,
            specific_heat=ALUMINUM_SPECIFIC_HEAT,
        )
    else:
        h_A_cooling_rate = 1.0

    if heating_results:
        avg_plate_temp_heating = np.mean([(r['T_start_f'] + r['T_end_f'])/2 for r in heating_results])
        h_A_heating_rate = calculate_h_A_from_rate(
            dT_dt=avg_heating_rate,
            T_plate=avg_plate_temp_heating,
            T_source=assumed_hot_gas_temp,
            mass_kg=recommended_mass,
            specific_heat=ALUMINUM_SPECIFIC_HEAT,
        )
    else:
        h_A_heating_rate = 3.0

    h_refrigerant_rate = h_A_cooling_rate / evaporator_area if h_A_cooling_rate else 50.0
    h_hotgas_rate = h_A_heating_rate / evaporator_area if h_A_heating_rate else 150.0

    print(f"""
Based on the observed thermal dynamics (RATE-BASED ANALYSIS):

@dataclass
class SimulatorParams:
    # Temperatures (°F) - standard refrigeration values
    refrigerant_temp_f: float = {assumed_refrigerant_temp:.1f}  # Evaporator temperature
    hot_gas_temp_f: float = {assumed_hot_gas_temp:.1f}  # Hot gas bypass temperature

    # Heat transfer coefficients (W/m²·K) - fitted from real data
    h_refrigerant: float = {h_refrigerant_rate:.1f}  # From cooling rate {avg_cooling_rate:.3f}°F/s
    h_hotgas: float = {h_hotgas_rate:.1f}  # From heating rate {avg_heating_rate:.3f}°F/s

    # Plate parameters
    plate_mass_kg: float = {recommended_mass}
    evaporator_area: float = {evaporator_area}

    # Observed rates:
    #   Cooling: {avg_cooling_rate:.3f}°F/s ({avg_cooling_rate*60:.1f}°F/min)
    #   Heating: {avg_heating_rate:.3f}°F/s ({avg_heating_rate*60:.1f}°F/min)

    # Observed time constants (from exponential fit):
    #   Cooling: τ = {avg_cooling_tau:.1f}s
    #   Heating: τ = {avg_heating_tau:.1f}s
""")

    # Validation: calculate expected cycle times
    print("=" * 70)
    print("VALIDATION: Expected vs Actual Cycle Times")
    print("=" * 70)

    # Get actual cycle times from data
    if cooling_results:
        actual_cooling_time = cooling_results[0]['duration_s']
        actual_temp_drop = abs(cooling_results[0]['T_change_f'])
    else:
        actual_cooling_time = 0
        actual_temp_drop = 0

    if heating_results:
        actual_heating_time = heating_results[0]['duration_s']
        actual_temp_rise = abs(heating_results[0]['T_change_f'])
    else:
        actual_heating_time = 0
        actual_temp_rise = 0

    print(f"""
Actual measured values:
  - First cooling cycle: {actual_cooling_time:.0f}s for {actual_temp_drop:.1f}°F drop
  - First heating cycle: {actual_heating_time:.0f}s for {actual_temp_rise:.1f}°F rise

With the fitted parameters (m={recommended_mass}kg, A={evaporator_area}m²):
  - Expected cooling rate: {avg_cooling_rate:.3f}°F/s
  - Expected heating rate: {avg_heating_rate:.3f}°F/s
  - Time for 56°F cooling (54→-2°F): {56/avg_cooling_rate:.0f}s (actual: {actual_cooling_time:.0f}s)
  - Time for 42°F heating (-2→40°F): {42/avg_heating_rate:.0f}s (actual: {actual_heating_time:.0f}s)
""")

    # Comparison with current simulation parameters
    print("=" * 70)
    print("COMPARISON WITH CURRENT SIMULATION")
    print("=" * 70)

    # Current values from physics_model.py
    current_params = {
        'h_refrigerant': 350.0,
        'h_hotgas': 80.0,
        'plate_mass_kg': 0.5,
        'evaporator_area': 0.02,
        'refrigerant_temp_f': -20.0,
        'hot_gas_temp_f': 140.0,
    }

    print(f"""
Current simulation parameters (from physics_model.py):
  h_refrigerant: {current_params['h_refrigerant']:.1f} W/(m²·K)
  h_hotgas: {current_params['h_hotgas']:.1f} W/(m²·K)
  plate_mass_kg: {current_params['plate_mass_kg']:.1f} kg
  evaporator_area: {current_params['evaporator_area']:.3f} m²

Recommended parameters (from real data analysis):
  h_refrigerant: {h_refrigerant_rate:.1f} W/(m²·K)  ({'%.1fx' % (h_refrigerant_rate/current_params['h_refrigerant'])} of current)
  h_hotgas: {h_hotgas_rate:.1f} W/(m²·K)  ({'%.1fx' % (h_hotgas_rate/current_params['h_hotgas'])} of current)
  plate_mass_kg: {recommended_mass:.1f} kg  ({'%.1fx' % (recommended_mass/current_params['plate_mass_kg'])} of current)
  evaporator_area: {evaporator_area:.3f} m² (unchanged)

Key insight: The current simulation cools {'%.1fx' % (current_params['h_refrigerant']/h_refrigerant_rate)} too fast
and heats {'%.1fx' % (h_hotgas_rate/current_params['h_hotgas'])} too slow compared to real hardware.
""")

    # Summary statistics
    print("=" * 70)
    print("DATA SUMMARY")
    print("=" * 70)

    # Find temperature ranges
    all_plate_temps = [dp.plate_temp_f for dp in data]
    all_bin_temps = [dp.bin_temp_f for dp in data]

    print(f"\nPlate temperature range: {min(all_plate_temps):.1f}°F to {max(all_plate_temps):.1f}°F")
    print(f"Bin temperature range: {min(all_bin_temps):.1f}°F to {max(all_bin_temps):.1f}°F")

    # Duration
    total_duration = (data[-1].timestamp - data[0].timestamp).total_seconds()
    print(f"Total recording duration: {total_duration:.0f}s ({total_duration/60:.1f} minutes)")

    # Cycle count
    max_cycle = max(dp.cycle_count for dp in data)
    print(f"Cycles completed: {max_cycle}")


if __name__ == "__main__":
    main()
