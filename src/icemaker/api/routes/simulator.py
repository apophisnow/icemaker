"""Simulator control API routes."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

if TYPE_CHECKING:
    from ..app import AppState

router = APIRouter()


def get_app_state() -> "AppState":
    """Get app state - injected at runtime."""
    from ..app import app_state
    return app_state


class SimulatorStatus(BaseModel):
    """Simulator status response."""
    enabled: bool
    speed_multiplier: float
    water_temp_f: float
    plate_temp_f: float
    bin_temp_f: float
    ice_thickness_mm: float = 0.0
    bin_fill_percent: float = 0.0
    bin_ice_mass_kg: float = 0.0


class SpeedRequest(BaseModel):
    """Speed multiplier request."""
    multiplier: float


@router.get("/", response_model=SimulatorStatus)
async def get_simulator_status() -> SimulatorStatus:
    """Get simulator status and current state."""
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

    model = state.controller._thermal_model
    if model is None:
        return SimulatorStatus(
            enabled=False,
            speed_multiplier=1.0,
            water_temp_f=0.0,
            plate_temp_f=0.0,
            bin_temp_f=0.0,
        )

    return SimulatorStatus(
        enabled=True,
        speed_multiplier=model.get_speed_multiplier(),
        water_temp_f=model.get_water_temp(),
        plate_temp_f=model.plate.temp_f,
        bin_temp_f=model.ice_bin.temp_f,
        ice_thickness_mm=model.get_ice_thickness_mm(),
        bin_fill_percent=model.get_bin_fill_percent(),
        bin_ice_mass_kg=model.get_bin_ice_mass_kg(),
    )


@router.get("/water-temp")
async def get_water_temperature() -> dict:
    """Get water reservoir temperature."""
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

    model = state.controller._thermal_model
    if model is None:
        raise HTTPException(400, "Simulator not enabled")

    return {
        "water_temp_f": model.get_water_temp(),
        "water_volume_liters": model.reservoir.volume_liters,
    }


@router.get("/speed")
async def get_speed_multiplier() -> dict:
    """Get current simulation speed multiplier."""
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

    model = state.controller._thermal_model
    if model is None:
        raise HTTPException(400, "Simulator not enabled")

    return {
        "speed_multiplier": model.get_speed_multiplier(),
    }


@router.post("/speed")
async def set_speed_multiplier(request: SpeedRequest) -> dict:
    """Set simulation speed multiplier.

    Args:
        request: Speed multiplier request.
            - 1.0 = realtime
            - 10.0 = 10x faster (1 minute in 6 seconds)
            - 60.0 = 60x faster (1 minute per second)
    """
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

    model = state.controller._thermal_model
    if model is None:
        raise HTTPException(400, "Simulator not enabled")

    model.set_speed_multiplier(request.multiplier)

    return {
        "speed_multiplier": model.get_speed_multiplier(),
        "message": f"Speed set to {model.get_speed_multiplier():.1f}x",
    }


@router.post("/reset")
async def reset_simulator() -> dict:
    """Reset simulator to initial state (room temperature)."""
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

    model = state.controller._thermal_model
    if model is None:
        raise HTTPException(400, "Simulator not enabled")

    model.reset()

    return {
        "message": "Simulator reset to initial state",
        "plate_temp_f": model.plate.temp_f,
        "bin_temp_f": model.ice_bin.temp_f,
        "water_temp_f": model.reservoir.temp_f,
        "bin_fill_percent": model.get_bin_fill_percent(),
    }
