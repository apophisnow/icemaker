"""Relay control API routes."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from ...hal.base import RelayName
from ..schemas import RelayCommand, RelayState

if TYPE_CHECKING:
    from ..app import AppState

router = APIRouter()


def get_app_state() -> "AppState":
    """Get app state - injected at runtime."""
    from ..app import app_state
    return app_state


@router.get("/", response_model=RelayState)
async def get_relay_states() -> RelayState:
    """Get current state of all relays."""
    state = get_app_state()
    if state.controller is None or state.controller.gpio is None:
        raise HTTPException(503, "Controller not initialized")

    relay_states = await state.controller.gpio.get_all_relays()

    # Convert RelayName enum keys to strings
    return RelayState(
        relays={relay.value: on for relay, on in relay_states.items()}
    )


@router.post("/")
async def set_relay(command: RelayCommand) -> dict:
    """Set a single relay state.

    Warning: Manual relay control can interfere with the state machine.
    Use with caution.

    Args:
        command: Relay name and desired state.

    Returns:
        Result of command.
    """
    state = get_app_state()
    if state.controller is None or state.controller.gpio is None:
        raise HTTPException(503, "Controller not initialized")

    # Validate relay name
    try:
        relay = RelayName(command.relay)
    except ValueError:
        valid_relays = [r.value for r in RelayName]
        raise HTTPException(
            400,
            f"Invalid relay: {command.relay}. Valid relays: {valid_relays}",
        )

    await state.controller.gpio.set_relay(relay, command.on)

    # Broadcast relay update
    relay_states = await state.controller.gpio.get_all_relays()
    await state.ws_manager.broadcast_relay_update({
        r.value: on for r, on in relay_states.items()
    })

    return {
        "success": True,
        "relay": command.relay,
        "state": command.on,
    }


@router.post("/all-off")
async def all_relays_off() -> dict:
    """Turn off all relays.

    Safe operation that can be used in emergencies.

    Returns:
        Result of command.
    """
    state = get_app_state()
    if state.controller is None or state.controller.gpio is None:
        raise HTTPException(503, "Controller not initialized")

    for relay in RelayName:
        await state.controller.gpio.set_relay(relay, False)

    # Broadcast relay update
    await state.ws_manager.broadcast_relay_update({
        r.value: False for r in RelayName
    })

    return {"success": True, "message": "All relays turned off"}
