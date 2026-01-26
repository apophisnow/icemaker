"""Configuration API routes."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING

from quart import Blueprint, abort, request

from ...config import load_config, reset_to_factory_defaults, save_runtime_config
from ..schemas import CONFIG_SCHEMA, ConfigResponse, ConfigUpdate

if TYPE_CHECKING:
    from ..app import AppState

bp = Blueprint("config", __name__)


def get_app_state() -> "AppState":
    """Get app state - injected at runtime."""
    from ..app import app_state
    return app_state


@bp.route("/schema")
async def get_config_schema():
    """Get configuration schema with field metadata.

    Returns the single source of truth for all configuration options,
    including their types, constraints, and descriptions.
    """
    return {
        "fields": [asdict(field) for field in CONFIG_SCHEMA],
        "categories": ["priming", "chill", "ice", "harvest", "rechill", "idle", "standby", "system"],
    }


@bp.route("/")
async def get_config():
    """Get current configuration."""
    state = get_app_state()
    if state.controller is None:
        abort(503, description="Controller not initialized")

    config = state.controller.config

    return asdict(ConfigResponse(
        prechill_temp=config.prechill.target_temp,
        prechill_timeout=config.prechill.timeout_seconds,
        ice_target_temp=config.ice_making.target_temp,
        ice_timeout=config.ice_making.timeout_seconds,
        harvest_threshold=config.harvest.target_temp,
        harvest_timeout=config.harvest.timeout_seconds,
        harvest_fill_time=config.harvest_fill_time,
        rechill_temp=config.rechill.target_temp,
        rechill_timeout=config.rechill.timeout_seconds,
        bin_full_threshold=config.bin_full_threshold,
        poll_interval=config.poll_interval,
        standby_timeout=config.standby_timeout,
        use_simulator=config.use_simulator,
        priming_enabled=config.priming_enabled,
        priming_flush_time=config.priming.flush_time_seconds,
        priming_pump_time=config.priming.pump_time_seconds,
        priming_fill_time=config.priming.fill_time_seconds,
    ))


@bp.route("/", methods=["PUT"])
async def update_config():
    """Update configuration and persist to runtime config file."""
    state = get_app_state()
    if state.controller is None:
        abort(503, description="Controller not initialized")

    data = await request.get_json()
    update = ConfigUpdate(
        prechill_temp=data.get("prechill_temp"),
        prechill_timeout=data.get("prechill_timeout"),
        ice_target_temp=data.get("ice_target_temp"),
        ice_timeout=data.get("ice_timeout"),
        harvest_threshold=data.get("harvest_threshold"),
        harvest_timeout=data.get("harvest_timeout"),
        harvest_fill_time=data.get("harvest_fill_time"),
        rechill_temp=data.get("rechill_temp"),
        rechill_timeout=data.get("rechill_timeout"),
        bin_full_threshold=data.get("bin_full_threshold"),
        standby_timeout=data.get("standby_timeout"),
        priming_enabled=data.get("priming_enabled"),
        priming_flush_time=data.get("priming_flush_time"),
        priming_pump_time=data.get("priming_pump_time"),
        priming_fill_time=data.get("priming_fill_time"),
    )

    config = state.controller.config

    # Apply updates
    if update.prechill_temp is not None:
        config.prechill.target_temp = update.prechill_temp
    if update.prechill_timeout is not None:
        config.prechill.timeout_seconds = update.prechill_timeout
    if update.ice_target_temp is not None:
        config.ice_making.target_temp = update.ice_target_temp
    if update.ice_timeout is not None:
        config.ice_making.timeout_seconds = update.ice_timeout
    if update.harvest_threshold is not None:
        config.harvest.target_temp = update.harvest_threshold
    if update.harvest_timeout is not None:
        config.harvest.timeout_seconds = update.harvest_timeout
    if update.harvest_fill_time is not None:
        config.harvest_fill_time = update.harvest_fill_time
    if update.rechill_temp is not None:
        config.rechill.target_temp = update.rechill_temp
    if update.rechill_timeout is not None:
        config.rechill.timeout_seconds = update.rechill_timeout
    if update.bin_full_threshold is not None:
        config.bin_full_threshold = update.bin_full_threshold
    if update.standby_timeout is not None:
        config.standby_timeout = update.standby_timeout
    if update.priming_enabled is not None:
        config.priming_enabled = update.priming_enabled
    if update.priming_flush_time is not None:
        config.priming.flush_time_seconds = update.priming_flush_time
    if update.priming_pump_time is not None:
        config.priming.pump_time_seconds = update.priming_pump_time
    if update.priming_fill_time is not None:
        config.priming.fill_time_seconds = update.priming_fill_time

    # Persist changes to runtime config file
    save_runtime_config(config)

    return asdict(ConfigResponse(
        prechill_temp=config.prechill.target_temp,
        prechill_timeout=config.prechill.timeout_seconds,
        ice_target_temp=config.ice_making.target_temp,
        ice_timeout=config.ice_making.timeout_seconds,
        harvest_threshold=config.harvest.target_temp,
        harvest_timeout=config.harvest.timeout_seconds,
        harvest_fill_time=config.harvest_fill_time,
        rechill_temp=config.rechill.target_temp,
        rechill_timeout=config.rechill.timeout_seconds,
        bin_full_threshold=config.bin_full_threshold,
        poll_interval=config.poll_interval,
        standby_timeout=config.standby_timeout,
        use_simulator=config.use_simulator,
        priming_enabled=config.priming_enabled,
        priming_flush_time=config.priming.flush_time_seconds,
        priming_pump_time=config.priming.pump_time_seconds,
        priming_fill_time=config.priming.fill_time_seconds,
    ))


@bp.route("/reset", methods=["POST"])
async def reset_config():
    """Reset configuration to factory defaults.

    Removes the runtime config file and reloads factory defaults.
    """
    state = get_app_state()
    if state.controller is None:
        abort(503, description="Controller not initialized")

    config = state.controller.config

    # Remove runtime config file
    reset_to_factory_defaults(config.data_dir)

    # Reload factory defaults (without runtime config overlay)
    factory_config = load_config()

    # Apply factory settings to running config (user-modifiable settings only)
    config.prechill.target_temp = factory_config.prechill.target_temp
    config.prechill.timeout_seconds = factory_config.prechill.timeout_seconds
    config.ice_making.target_temp = factory_config.ice_making.target_temp
    config.ice_making.timeout_seconds = factory_config.ice_making.timeout_seconds
    config.harvest.target_temp = factory_config.harvest.target_temp
    config.harvest.timeout_seconds = factory_config.harvest.timeout_seconds
    config.harvest_fill_time = factory_config.harvest_fill_time
    config.rechill.target_temp = factory_config.rechill.target_temp
    config.rechill.timeout_seconds = factory_config.rechill.timeout_seconds
    config.bin_full_threshold = factory_config.bin_full_threshold
    config.standby_timeout = factory_config.standby_timeout
    config.priming_enabled = factory_config.priming_enabled
    config.priming.flush_time_seconds = factory_config.priming.flush_time_seconds
    config.priming.pump_time_seconds = factory_config.priming.pump_time_seconds
    config.priming.fill_time_seconds = factory_config.priming.fill_time_seconds

    return asdict(ConfigResponse(
        prechill_temp=config.prechill.target_temp,
        prechill_timeout=config.prechill.timeout_seconds,
        ice_target_temp=config.ice_making.target_temp,
        ice_timeout=config.ice_making.timeout_seconds,
        harvest_threshold=config.harvest.target_temp,
        harvest_timeout=config.harvest.timeout_seconds,
        harvest_fill_time=config.harvest_fill_time,
        rechill_temp=config.rechill.target_temp,
        rechill_timeout=config.rechill.timeout_seconds,
        bin_full_threshold=config.bin_full_threshold,
        poll_interval=config.poll_interval,
        standby_timeout=config.standby_timeout,
        use_simulator=config.use_simulator,
        priming_enabled=config.priming_enabled,
        priming_flush_time=config.priming.flush_time_seconds,
        priming_pump_time=config.priming.pump_time_seconds,
        priming_fill_time=config.priming.fill_time_seconds,
    ))
