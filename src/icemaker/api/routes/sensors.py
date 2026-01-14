"""Temperature sensor API routes."""

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from ...hal.base import SensorName
from ..schemas import TemperatureReading

if TYPE_CHECKING:
    from ..app import AppState

router = APIRouter()


def get_app_state() -> "AppState":
    """Get app state - injected at runtime."""
    from ..app import app_state
    return app_state


@router.get("/", response_model=TemperatureReading)
async def get_temperatures() -> TemperatureReading:
    """Get current temperature readings from all sensors."""
    state = get_app_state()
    if state.controller is None or state.controller.sensors is None:
        raise HTTPException(503, "Controller not initialized")

    temps = await state.controller.sensors.read_all_temperatures()

    return TemperatureReading(
        plate_temp_f=temps.get(SensorName.PLATE, 0.0),
        bin_temp_f=temps.get(SensorName.ICE_BIN, 0.0),
        timestamp=datetime.now(),
    )


@router.get("/plate")
async def get_plate_temperature() -> dict:
    """Get plate temperature."""
    state = get_app_state()
    if state.controller is None or state.controller.sensors is None:
        raise HTTPException(503, "Controller not initialized")

    temp = await state.controller.sensors.read_temperature(SensorName.PLATE)

    return {
        "sensor": "plate",
        "temperature_f": temp,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/bin")
async def get_bin_temperature() -> dict:
    """Get ice bin temperature."""
    state = get_app_state()
    if state.controller is None or state.controller.sensors is None:
        raise HTTPException(503, "Controller not initialized")

    temp = await state.controller.sensors.read_temperature(SensorName.ICE_BIN)

    return {
        "sensor": "ice_bin",
        "temperature_f": temp,
        "timestamp": datetime.now().isoformat(),
    }
