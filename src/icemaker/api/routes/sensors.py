"""Temperature sensor API routes."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import TYPE_CHECKING

from quart import Blueprint, abort

from ...hal.base import SensorName
from ..schemas import TemperatureReading

if TYPE_CHECKING:
    from ..app import AppState

bp = Blueprint("sensors", __name__)


def get_app_state() -> "AppState":
    """Get app state - injected at runtime."""
    from ..app import app_state
    return app_state


def _serialize_temp_reading(reading: TemperatureReading) -> dict:
    """Serialize TemperatureReading to JSON-compatible dict."""
    data = asdict(reading)
    data["timestamp"] = data["timestamp"].isoformat()
    return data


@bp.route("/")
async def get_temperatures():
    """Get current temperature readings from all sensors."""
    state = get_app_state()
    if state.controller is None or state.controller.sensors is None:
        abort(503, description="Controller not initialized")

    temps = await state.controller.sensors.read_all_temperatures()

    return _serialize_temp_reading(TemperatureReading(
        plate_temp_f=temps.get(SensorName.PLATE, 0.0),
        bin_temp_f=temps.get(SensorName.ICE_BIN, 0.0),
        timestamp=datetime.now(),
    ))


@bp.route("/plate")
async def get_plate_temperature():
    """Get plate temperature."""
    state = get_app_state()
    if state.controller is None or state.controller.sensors is None:
        abort(503, description="Controller not initialized")

    temp = await state.controller.sensors.read_temperature(SensorName.PLATE)

    return {
        "sensor": "plate",
        "temperature_f": temp,
        "timestamp": datetime.now().isoformat(),
    }


@bp.route("/bin")
async def get_bin_temperature():
    """Get ice bin temperature."""
    state = get_app_state()
    if state.controller is None or state.controller.sensors is None:
        abort(503, description="Controller not initialized")

    temp = await state.controller.sensors.read_temperature(SensorName.ICE_BIN)

    return {
        "sensor": "ice_bin",
        "temperature_f": temp,
        "timestamp": datetime.now().isoformat(),
    }
