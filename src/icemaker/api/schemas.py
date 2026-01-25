"""Pydantic models for API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class StateResponse(BaseModel):
    """Current icemaker state response."""

    state: str
    previous_state: Optional[str] = None
    state_enter_time: datetime
    cycle_count: int
    plate_temp: float
    bin_temp: float
    target_temp: Optional[float] = None
    time_in_state_seconds: float
    chill_mode: Optional[str] = None


class RelayState(BaseModel):
    """State of all relays."""

    relays: dict[str, bool]


class RelayCommand(BaseModel):
    """Command to set a single relay state."""

    relay: str
    on: bool


class TemperatureReading(BaseModel):
    """Temperature sensor readings."""

    plate_temp_f: float
    bin_temp_f: float
    timestamp: datetime = Field(default_factory=datetime.now)


class StateTransitionRequest(BaseModel):
    """Request to transition to a new state."""

    target_state: str
    force: bool = False


class ConfigResponse(BaseModel):
    """Current configuration response."""

    prechill_temp: float
    prechill_timeout: int
    ice_target_temp: float
    ice_timeout: int
    harvest_threshold: float
    harvest_timeout: int
    rechill_temp: float
    rechill_timeout: int
    bin_full_threshold: float
    poll_interval: float
    use_simulator: bool


class ConfigUpdate(BaseModel):
    """Configuration update request."""

    prechill_temp: Optional[float] = None
    prechill_timeout: Optional[int] = None
    ice_target_temp: Optional[float] = None
    ice_timeout: Optional[int] = None
    harvest_threshold: Optional[float] = None
    harvest_timeout: Optional[int] = None
    rechill_temp: Optional[float] = None
    rechill_timeout: Optional[int] = None
    bin_full_threshold: Optional[float] = None


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str  # "state_update", "temp_update", "relay_update", "error"
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


class CycleCommand(BaseModel):
    """Command to control ice-making cycle."""

    action: str  # "start", "stop", "emergency_stop"


class ErrorResponse(BaseModel):
    """Error response."""

    error: str
    detail: Optional[str] = None
