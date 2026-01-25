"""Data classes for API request/response schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class StateResponse:
    """Current icemaker state response."""

    state: str
    state_enter_time: datetime
    cycle_count: int
    plate_temp: float
    bin_temp: float
    time_in_state_seconds: float
    previous_state: Optional[str] = None
    target_temp: Optional[float] = None
    chill_mode: Optional[str] = None


@dataclass
class RelayState:
    """State of all relays."""

    relays: dict[str, bool]


@dataclass
class RelayCommand:
    """Command to set a single relay state."""

    relay: str
    on: bool


@dataclass
class TemperatureReading:
    """Temperature sensor readings."""

    plate_temp_f: float
    bin_temp_f: float
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StateTransitionRequest:
    """Request to transition to a new state."""

    target_state: str
    force: bool = False


@dataclass
class ConfigResponse:
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


@dataclass
class ConfigUpdate:
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


@dataclass
class WebSocketMessage:
    """WebSocket message format."""

    type: str  # "state_update", "temp_update", "relay_update", "error"
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CycleCommand:
    """Command to control ice-making cycle."""

    action: str  # "start", "stop", "emergency_stop"


@dataclass
class ErrorResponse:
    """Error response."""

    error: str
    detail: Optional[str] = None
