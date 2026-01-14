"""Configuration API routes."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from ..schemas import ConfigResponse, ConfigUpdate

if TYPE_CHECKING:
    from ..app import AppState

router = APIRouter()


def get_app_state() -> "AppState":
    """Get app state - injected at runtime."""
    from ..app import app_state
    return app_state


@router.get("/", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    """Get current configuration."""
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

    config = state.controller.config

    return ConfigResponse(
        prechill_temp=config.prechill.target_temp,
        prechill_timeout=config.prechill.timeout_seconds,
        ice_target_temp=config.ice_making.target_temp,
        ice_timeout=config.ice_making.timeout_seconds,
        harvest_threshold=config.harvest.target_temp,
        harvest_timeout=config.harvest.timeout_seconds,
        rechill_temp=config.rechill.target_temp,
        rechill_timeout=config.rechill.timeout_seconds,
        bin_full_threshold=config.bin_full_threshold,
        poll_interval=config.poll_interval,
        use_simulator=config.use_simulator,
    )


@router.put("/")
async def update_config(update: ConfigUpdate) -> ConfigResponse:
    """Update configuration.

    Note: Changes are applied to the running controller but not
    persisted to configuration files.

    Args:
        update: Configuration values to update.

    Returns:
        Updated configuration.
    """
    state = get_app_state()
    if state.controller is None:
        raise HTTPException(503, "Controller not initialized")

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
    if update.rechill_temp is not None:
        config.rechill.target_temp = update.rechill_temp
    if update.rechill_timeout is not None:
        config.rechill.timeout_seconds = update.rechill_timeout
    if update.bin_full_threshold is not None:
        config.bin_full_threshold = update.bin_full_threshold

    return ConfigResponse(
        prechill_temp=config.prechill.target_temp,
        prechill_timeout=config.prechill.timeout_seconds,
        ice_target_temp=config.ice_making.target_temp,
        ice_timeout=config.ice_making.timeout_seconds,
        harvest_threshold=config.harvest.target_temp,
        harvest_timeout=config.harvest.timeout_seconds,
        rechill_temp=config.rechill.target_temp,
        rechill_timeout=config.rechill.timeout_seconds,
        bin_full_threshold=config.bin_full_threshold,
        poll_interval=config.poll_interval,
        use_simulator=config.use_simulator,
    )
