"""State API routes."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from quart import Blueprint, abort, request, websocket

from ..schemas import CycleCommand, StateResponse, StateTransitionRequest

if TYPE_CHECKING:
    from ..app import AppState

bp = Blueprint("state", __name__)


def get_app_state() -> "AppState":
    """Get app state - injected at runtime."""
    from ..app import app_state
    return app_state


def _serialize_state_response(response: StateResponse) -> dict:
    """Serialize StateResponse to JSON-compatible dict."""
    data = asdict(response)
    data["state_enter_time"] = data["state_enter_time"].isoformat()
    return data


@bp.route("/")
async def get_current_state():
    """Get current icemaker state."""
    state = get_app_state()
    if state.controller is None:
        abort(503, description="Controller not initialized")

    fsm = state.controller.fsm
    ctx = fsm.context

    response = StateResponse(
        state=fsm.state.name,
        previous_state=fsm.previous_state.name if fsm.previous_state else None,
        state_enter_time=ctx.state_enter_time,
        cycle_count=ctx.cycle_count,
        session_cycle_count=ctx.session_cycle_count,
        plate_temp=ctx.plate_temp,
        bin_temp=ctx.bin_temp,
        target_temp=ctx.target_temp,
        time_in_state_seconds=fsm.time_in_state(),
        chill_mode=ctx.chill_mode,
    )

    return _serialize_state_response(response)


@bp.route("/transition", methods=["POST"])
async def request_transition():
    """Request state transition."""
    state = get_app_state()
    if state.controller is None:
        abort(503, description="Controller not initialized")

    data = await request.get_json()
    req = StateTransitionRequest(
        target_state=data.get("target_state", ""),
        force=data.get("force", False),
    )

    from ...core.states import IcemakerState

    try:
        target = IcemakerState[req.target_state.upper()]
    except KeyError:
        abort(400, description=f"Invalid state: {req.target_state}")

    fsm = state.controller.fsm
    success = await fsm.transition_to(target)

    if not success and not req.force:
        abort(400, description=f"Cannot transition from {fsm.state.name} to {target.name}")

    return {"success": success, "new_state": fsm.state.name}


@bp.route("/cycle", methods=["POST"])
async def control_cycle():
    """Control ice-making cycle."""
    state = get_app_state()
    if state.controller is None:
        abort(503, description="Controller not initialized")

    data = await request.get_json()
    command = CycleCommand(action=data.get("action", ""))

    if command.action == "power_on":
        success = await state.controller.power_on()
        if not success:
            abort(400, description="Cannot power on - not in OFF state")
        return {"success": True, "message": "Power on initiated"}

    elif command.action == "power_off":
        success = await state.controller.power_off()
        if not success:
            abort(400, description="Cannot power off - not in IDLE or ERROR state")
        return {"success": True, "message": "Powered off"}

    elif command.action == "start":
        success = await state.controller.start_cycle()
        if not success:
            abort(400, description="Cannot start cycle - not in IDLE state")
        return {"success": True, "message": "Cycle started"}

    elif command.action == "stop":
        success = await state.controller.stop_cycle()
        if not success:
            abort(400, description="Cannot stop cycle - not in an active cycle state")
        return {"success": True, "message": "Cycle stopped"}

    elif command.action == "emergency_stop":
        await state.controller.emergency_stop()
        return {"success": True, "message": "Emergency stop executed"}

    elif command.action == "prepare_restart":
        # Save state for graceful restart (preserves relay states)
        await state.controller._save_state()
        return {
            "success": True,
            "message": "State saved for graceful restart. Stop the server and restart.",
            "current_state": state.controller.fsm.state.name,
        }

    else:
        abort(400, description=f"Invalid action: {command.action}")


@bp.websocket("/ws")
async def websocket_endpoint():
    """WebSocket endpoint for real-time updates."""
    state = get_app_state()
    await state.ws_manager.connect(websocket._get_current_object())
    try:
        while True:
            # Keep connection alive, handle incoming messages if needed
            data = await websocket.receive()
            # Could handle commands here in the future
    except Exception:
        await state.ws_manager.disconnect(websocket._get_current_object())
