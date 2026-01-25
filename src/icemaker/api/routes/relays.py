"""Relay control API routes."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from quart import Blueprint, abort, request

from ...hal.base import RelayName
from ..schemas import RelayCommand, RelayState

if TYPE_CHECKING:
    from ..app import AppState

bp = Blueprint("relays", __name__)


def get_app_state() -> "AppState":
    """Get app state - injected at runtime."""
    from ..app import app_state
    return app_state


@bp.route("/")
async def get_relay_states():
    """Get current state of all relays."""
    state = get_app_state()
    if state.controller is None or state.controller.gpio is None:
        abort(503, description="Controller not initialized")

    relay_states = await state.controller.gpio.get_all_relays()

    # Convert RelayName enum keys to strings
    return asdict(RelayState(
        relays={relay.value: on for relay, on in relay_states.items()}
    ))


@bp.route("/", methods=["POST"])
async def set_relay():
    """Set a single relay state.

    Warning: Manual relay control can interfere with the state machine.
    Use with caution.
    """
    state = get_app_state()
    if state.controller is None or state.controller.gpio is None:
        abort(503, description="Controller not initialized")

    data = await request.get_json()
    command = RelayCommand(
        relay=data.get("relay", ""),
        on=data.get("on", False),
    )

    # Validate relay name
    try:
        relay = RelayName(command.relay)
    except ValueError:
        valid_relays = [r.value for r in RelayName]
        abort(400, description=f"Invalid relay: {command.relay}. Valid relays: {valid_relays}")

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


@bp.route("/all-off", methods=["POST"])
async def all_relays_off():
    """Turn off all relays.

    Safe operation that can be used in emergencies.
    """
    state = get_app_state()
    if state.controller is None or state.controller.gpio is None:
        abort(503, description="Controller not initialized")

    for relay in RelayName:
        await state.controller.gpio.set_relay(relay, False)

    # Broadcast relay update
    await state.ws_manager.broadcast_relay_update({
        r.value: False for r in RelayName
    })

    return {"success": True, "message": "All relays turned off"}
