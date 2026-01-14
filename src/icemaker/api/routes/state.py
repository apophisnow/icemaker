"""State API routes."""

from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from ..schemas import CycleCommand, StateResponse, StateTransitionRequest

if TYPE_CHECKING:
    from ..app import AppState

router = APIRouter()


def get_app_state() -> "AppState":
    """Get app state - injected at runtime."""
    from ..app import app_state
    return app_state


@router.get("/", response_model=StateResponse)
async def get_current_state() -> StateResponse:
    """Get current icemaker state."""
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

    fsm = state.controller.fsm
    ctx = fsm.context

    return StateResponse(
        state=fsm.state.name,
        previous_state=fsm.previous_state.name if fsm.previous_state else None,
        state_enter_time=ctx.state_enter_time,
        cycle_count=ctx.cycle_count,
        plate_temp=ctx.plate_temp,
        bin_temp=ctx.bin_temp,
        target_temp=ctx.target_temp,
        time_in_state_seconds=fsm.time_in_state(),
        chill_mode=ctx.chill_mode,
    )


@router.post("/transition")
async def request_transition(request: StateTransitionRequest) -> dict:
    """Request state transition.

    Args:
        request: Transition request with target state.

    Returns:
        Result of transition attempt.
    """
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

    from ...core.states import IcemakerState

    try:
        target = IcemakerState[request.target_state.upper()]
    except KeyError:
        raise HTTPException(400, f"Invalid state: {request.target_state}")

    fsm = state.controller.fsm
    success = await fsm.transition_to(target)

    if not success and not request.force:
        raise HTTPException(
            400,
            f"Cannot transition from {fsm.state.name} to {target.name}",
        )

    return {"success": success, "new_state": fsm.state.name}


@router.post("/cycle")
async def control_cycle(command: CycleCommand) -> dict:
    """Control ice-making cycle.

    Args:
        command: Cycle control command (start, stop, emergency_stop).

    Returns:
        Result of command.
    """
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

    if command.action == "start":
        success = await state.controller.start_cycle()
        if not success:
            raise HTTPException(400, "Cannot start cycle - not in IDLE state")
        return {"success": True, "message": "Cycle started"}

    elif command.action == "stop":
        await state.controller.fsm.transition_to(
            state.controller.fsm.state.__class__.IDLE
        )
        return {"success": True, "message": "Cycle stopped"}

    elif command.action == "emergency_stop":
        await state.controller.emergency_stop()
        return {"success": True, "message": "Emergency stop executed"}

    else:
        raise HTTPException(400, f"Invalid action: {command.action}")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time updates."""
    state = get_app_state()
    await state.ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, handle incoming messages if needed
            data = await websocket.receive_text()
            # Could handle commands here in the future
    except WebSocketDisconnect:
        await state.ws_manager.disconnect(websocket)
