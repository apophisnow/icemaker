"""Quart application for icemaker control."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional

from quart import Quart
from quart_cors import cors

from ..config import load_config
from ..core.controller import IcemakerController
from ..core.events import Event, EventType
from ..hal.base import SensorName
from .websocket import WebSocketManager

logger = logging.getLogger(__name__)


@dataclass
class AppState:
    """Application state container."""

    controller: Optional[IcemakerController] = None
    ws_manager: WebSocketManager = field(default_factory=WebSocketManager)
    _controller_task: Optional[asyncio.Task] = None
    _sensor_task: Optional[asyncio.Task] = None
    _shutdown_event: asyncio.Event = field(default_factory=asyncio.Event)


# Global app state
app_state = AppState()


def _get_target_temp_for_state(state: str) -> float | None:
    """Get target temp for a state based on config."""
    controller = app_state.controller
    if controller is None:
        return None
    cfg = controller.config
    ctx = controller.fsm.context

    target = None
    if state == "CHILL":
        if ctx.chill_mode == "rechill":
            target = cfg.rechill.target_temp
        else:
            target = cfg.prechill.target_temp
    elif state == "ICE":
        target = cfg.ice_making.target_temp
    elif state == "HEAT":
        target = cfg.harvest.target_temp

    logger.debug("_get_target_temp_for_state(%s) -> %s (harvest=%s)", state, target, cfg.harvest.target_temp)
    return target


async def _event_handler(event: Event) -> None:
    """Handle FSM events and broadcast to WebSocket clients."""
    if event.type == EventType.STATE_ENTER:
        fsm = app_state.controller.fsm
        ctx = fsm.context
        state_name = event.data.get("state", "")

        # Get correct target temp for the new state
        target_temp = _get_target_temp_for_state(state_name)
        if target_temp is not None:
            ctx.target_temp = target_temp

        await app_state.ws_manager.broadcast_state_update(
            state=state_name,
            previous_state=event.data.get("from_state"),
            plate_temp=ctx.plate_temp,
            bin_temp=ctx.bin_temp,
            target_temp=ctx.target_temp,
            cycle_count=ctx.cycle_count,
            time_in_state=fsm.time_in_state(),
            chill_mode=ctx.chill_mode,
        )

    elif event.type == EventType.TEMP_READING:
        await app_state.ws_manager.broadcast_temp_update(
            plate_temp=event.data.get("plate_temp", 0.0),
            bin_temp=event.data.get("bin_temp", 0.0),
        )

    elif event.type == EventType.RELAY_CHANGED:
        # Get all relay states and broadcast
        if app_state.controller and app_state.controller.gpio:
            relay_states = await app_state.controller.gpio.get_all_relays()
            await app_state.ws_manager.broadcast_relay_update({
                r.value: on for r, on in relay_states.items()
            })

    elif event.type == EventType.ERROR:
        await app_state.ws_manager.broadcast_error(
            message=event.data.get("message", "Unknown error"),
            error_type=event.data.get("error_type"),
        )


async def _poll_sensors_loop() -> None:
    """Background task to poll temperature sensors."""
    controller = app_state.controller
    if controller is None or controller.sensors is None:
        return

    logger.info("Sensor polling started")
    while not app_state._shutdown_event.is_set():
        try:
            temps = await controller.sensors.read_all_temperatures()
            controller.fsm.context.plate_temp = temps.get(SensorName.PLATE, 70.0)
            controller.fsm.context.bin_temp = temps.get(SensorName.ICE_BIN, 70.0)

            # Get simulator data from thermal model if available
            water_temp = None
            simulated_time = None
            if controller._thermal_model is not None:
                water_temp = controller._thermal_model.get_water_temp()
                simulated_time = controller._thermal_model.get_simulated_time()

            # Broadcast temperature update via WebSocket
            await app_state.ws_manager.broadcast_temp_update(
                controller.fsm.context.plate_temp,
                controller.fsm.context.bin_temp,
                water_temp,
                controller.fsm.context.target_temp,
                simulated_time,
                controller.fsm.time_in_state(),
            )

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Sensor polling error: %s", e)

        try:
            await asyncio.wait_for(
                app_state._shutdown_event.wait(),
                timeout=controller.config.poll_interval,
            )
            break  # Shutdown requested
        except asyncio.TimeoutError:
            pass  # Normal timeout, continue polling

    logger.info("Sensor polling stopped")


async def _shutdown_tasks() -> None:
    """Clean up all background tasks."""
    logger.info("Shutting down icemaker API")

    # Signal all tasks to stop
    app_state._shutdown_event.set()

    # Stop the FSM
    if app_state.controller is not None:
        app_state.controller.fsm._running = False

    # Cancel and wait for controller task
    if app_state._controller_task is not None:
        app_state._controller_task.cancel()
        try:
            await asyncio.wait_for(app_state._controller_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    # Cancel and wait for sensor task
    if app_state._sensor_task is not None:
        app_state._sensor_task.cancel()
        try:
            await asyncio.wait_for(app_state._sensor_task, timeout=2.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass

    # Stop thermal model
    if app_state.controller is not None and app_state.controller._thermal_model is not None:
        await app_state.controller._thermal_model.stop()

    # Clean up hardware
    if app_state.controller is not None and app_state.controller.gpio is not None:
        try:
            await app_state.controller.gpio.cleanup()
        except Exception as e:
            logger.error("GPIO cleanup error: %s", e)

    logger.info("Icemaker API shutdown complete")


def create_app() -> Quart:
    """Create and configure the Quart application."""
    app = Quart(__name__)

    # CORS configuration for frontend
    app = cors(
        app,
        allow_origin=[
            "http://localhost:5173",  # Vite dev server
            "http://localhost:3000",  # Alternative dev port
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.before_serving
    async def startup() -> None:
        """Application startup."""
        global app_state

        # Reset shutdown event for fresh start
        app_state._shutdown_event = asyncio.Event()

        # Startup
        logger.info("Starting icemaker API")

        # Load configuration
        cfg = load_config()

        # Create controller (but don't initialize hardware yet)
        app_state.controller = IcemakerController(config=cfg)
        app_state.controller.add_event_listener(_event_handler)

        logger.info("Icemaker API ready, initializing hardware...")

        # Initialize hardware (HAL setup)
        await app_state.controller.initialize()

        # Start thermal model if using simulator
        if app_state.controller._thermal_model is not None:
            await app_state.controller._thermal_model.start()

        # Start FSM in background task
        app_state._controller_task = asyncio.create_task(
            app_state.controller.fsm.run(),
            name="fsm-controller",
        )

        # Start sensor polling in background task
        app_state._sensor_task = asyncio.create_task(
            _poll_sensors_loop(),
            name="sensor-polling",
        )

        logger.info("Icemaker API started")

    @app.after_serving
    async def shutdown() -> None:
        """Application shutdown."""
        await _shutdown_tasks()

    @app.route("/health")
    async def health_check():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "controller_running": app_state.controller is not None,
            "websocket_connections": app_state.ws_manager.connection_count,
        }

    # Register blueprints
    from .routes import config, relays, sensors, simulator, state

    app.register_blueprint(state.bp, url_prefix="/api/state")
    app.register_blueprint(config.bp, url_prefix="/api/config")
    app.register_blueprint(relays.bp, url_prefix="/api/relays")
    app.register_blueprint(sensors.bp, url_prefix="/api/sensors")
    app.register_blueprint(simulator.bp, url_prefix="/api/simulator")

    return app


# Create the app instance
app = create_app()
