"""WebSocket manager for real-time updates."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any

from quart import Websocket

from .schemas import WebSocketMessage

logger = logging.getLogger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts.

    Handles multiple client connections and broadcasts state updates,
    temperature readings, and relay changes to all connected clients.
    """

    def __init__(self) -> None:
        self._connections: list[Websocket] = []
        self._lock = asyncio.Lock()

    @property
    def connection_count(self) -> int:
        """Number of active WebSocket connections."""
        return len(self._connections)

    async def connect(self, websocket: Websocket) -> None:
        """Register a new WebSocket connection.

        Args:
            websocket: The WebSocket connection to register.
        """
        async with self._lock:
            self._connections.append(websocket)
        logger.info(
            "WebSocket connected. Total connections: %d",
            len(self._connections),
        )

    async def disconnect(self, websocket: Websocket) -> None:
        """Remove a WebSocket connection.

        Args:
            websocket: The WebSocket connection to remove.
        """
        async with self._lock:
            if websocket in self._connections:
                self._connections.remove(websocket)
        logger.info(
            "WebSocket disconnected. Total connections: %d",
            len(self._connections),
        )

    async def broadcast(self, message_type: str, data: dict[str, Any]) -> None:
        """Broadcast message to all connected clients.

        Automatically removes clients that fail to receive the message.

        Args:
            message_type: Type of message (e.g., "state_update").
            data: Message data dictionary.
        """
        if not self._connections:
            return

        message = WebSocketMessage(
            type=message_type,
            data=data,
            timestamp=datetime.now(),
        )

        # Convert dataclass to JSON, handling datetime serialization
        message_dict = asdict(message)
        message_dict["timestamp"] = message_dict["timestamp"].isoformat()
        json_message = json.dumps(message_dict)

        async with self._lock:
            disconnected: list[Websocket] = []
            for connection in self._connections:
                try:
                    await connection.send(json_message)
                except Exception as e:
                    logger.warning("Failed to send to WebSocket: %s", e)
                    disconnected.append(connection)

            for conn in disconnected:
                self._connections.remove(conn)

    async def broadcast_state_update(
        self,
        state: str,
        previous_state: str | None,
        plate_temp: float,
        bin_temp: float,
        target_temp: float | None,
        cycle_count: int,
        session_cycle_count: int,
        time_in_state: float,
        chill_mode: str | None = None,
    ) -> None:
        """Broadcast state update to all clients.

        Args:
            state: Current state name.
            previous_state: Previous state name.
            plate_temp: Current plate temperature.
            bin_temp: Current bin temperature.
            target_temp: Target temperature for current state.
            cycle_count: Lifetime cycle count.
            session_cycle_count: Session cycle count (since server start).
            time_in_state: Seconds in current state.
            chill_mode: Current chill mode if in CHILL state.
        """
        await self.broadcast("state_update", {
            "state": state,
            "previous_state": previous_state,
            "plate_temp": plate_temp,
            "bin_temp": bin_temp,
            "target_temp": target_temp,
            "cycle_count": cycle_count,
            "session_cycle_count": session_cycle_count,
            "time_in_state_seconds": time_in_state,
            "chill_mode": chill_mode,
        })

    async def broadcast_temp_update(
        self,
        plate_temp: float,
        bin_temp: float,
        water_temp: float | None = None,
        target_temp: float | None = None,
        simulated_time_seconds: float | None = None,
        time_in_state_seconds: float | None = None,
    ) -> None:
        """Broadcast temperature update to all clients.

        Args:
            plate_temp: Current plate temperature in Fahrenheit.
            bin_temp: Current bin temperature in Fahrenheit.
            water_temp: Current water reservoir temperature in Fahrenheit (simulator only).
            target_temp: Current target temperature for the state.
            simulated_time_seconds: Elapsed simulated time in seconds (simulator only).
            time_in_state_seconds: Seconds in current state (uses simulated time in simulator mode).
        """
        data = {
            "plate_temp_f": plate_temp,
            "bin_temp_f": bin_temp,
        }
        if water_temp is not None:
            data["water_temp_f"] = water_temp
        if target_temp is not None:
            data["target_temp"] = target_temp
        if simulated_time_seconds is not None:
            data["simulated_time_seconds"] = simulated_time_seconds
        if time_in_state_seconds is not None:
            data["time_in_state_seconds"] = time_in_state_seconds
        await self.broadcast("temp_update", data)

    async def broadcast_relay_update(
        self,
        relays: dict[str, bool],
    ) -> None:
        """Broadcast relay state update to all clients.

        Args:
            relays: Dictionary of relay names to states.
        """
        await self.broadcast("relay_update", {"relays": relays})

    async def broadcast_error(
        self,
        message: str,
        error_type: str | None = None,
    ) -> None:
        """Broadcast error message to all clients.

        Args:
            message: Error message.
            error_type: Optional error classification.
        """
        data: dict[str, Any] = {"message": message}
        if error_type:
            data["error_type"] = error_type
        await self.broadcast("error", data)
