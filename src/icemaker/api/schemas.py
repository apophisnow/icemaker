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
    cycle_count: int  # Lifetime cycle count
    session_cycle_count: int  # Session cycle count (since server start)
    plate_temp: float
    bin_temp: float
    time_in_state_seconds: float
    previous_state: Optional[str] = None
    target_temp: Optional[float] = None
    chill_mode: Optional[str] = None
    shutdown_requested: bool = False  # Graceful shutdown in progress


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
    harvest_fill_time: int
    rechill_temp: float
    rechill_timeout: int
    bin_full_threshold: float
    poll_interval: float
    standby_timeout: float
    use_simulator: bool
    priming_enabled: bool
    priming_flush_time: int
    priming_pump_time: int
    priming_fill_time: int


@dataclass
class ConfigUpdate:
    """Configuration update request."""

    prechill_temp: Optional[float] = None
    prechill_timeout: Optional[int] = None
    ice_target_temp: Optional[float] = None
    ice_timeout: Optional[int] = None
    harvest_threshold: Optional[float] = None
    harvest_timeout: Optional[int] = None
    harvest_fill_time: Optional[int] = None
    rechill_temp: Optional[float] = None
    rechill_timeout: Optional[int] = None
    bin_full_threshold: Optional[float] = None
    standby_timeout: Optional[float] = None
    priming_enabled: Optional[bool] = None
    priming_flush_time: Optional[int] = None
    priming_pump_time: Optional[int] = None
    priming_fill_time: Optional[int] = None


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


@dataclass
class ConfigFieldSchema:
    """Schema for a single configuration field."""

    key: str
    name: str
    description: str
    type: str  # "float", "int", "bool"
    category: str  # State-based: "chill", "ice", "harvest", "rechill", "idle", "standby", "priming", "system"
    unit: Optional[str] = None  # "°F", "seconds", etc.
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    step: Optional[float] = None
    default: Any = None
    readonly: bool = False


# Single source of truth for all config field metadata
# Organized by the state/phase each setting applies to (in execution order)
CONFIG_SCHEMA: list[ConfigFieldSchema] = [
    # POWER_ON state (priming) - runs first when enabled
    ConfigFieldSchema(
        key="priming_enabled",
        name="Enable Priming",
        description="Run water priming sequence on startup",
        type="bool",
        category="priming",
        default=False,
    ),
    ConfigFieldSchema(
        key="priming_flush_time",
        name="1. Flush Time",
        description="Duration of initial water flush",
        type="int",
        category="priming",
        unit="seconds",
        min_value=10,
        max_value=180,
        step=5,
        default=60,
    ),
    ConfigFieldSchema(
        key="priming_pump_time",
        name="2. Pump Time",
        description="Duration of pump operation during priming",
        type="int",
        category="priming",
        unit="seconds",
        min_value=5,
        max_value=60,
        step=5,
        default=15,
    ),
    ConfigFieldSchema(
        key="priming_fill_time",
        name="3. Fill Time",
        description="Duration of water fill during priming",
        type="int",
        category="priming",
        unit="seconds",
        min_value=5,
        max_value=60,
        step=5,
        default=15,
    ),
    # CHILL state (prechill phase)
    ConfigFieldSchema(
        key="prechill_temp",
        name="Target Temperature",
        description="Target plate temperature before ice making begins",
        type="float",
        category="chill",
        unit="°F",
        min_value=20.0,
        max_value=50.0,
        step=0.5,
        default=32.0,
    ),
    ConfigFieldSchema(
        key="prechill_timeout",
        name="Timeout",
        description="Maximum time allowed for prechill phase",
        type="int",
        category="chill",
        unit="seconds",
        min_value=30,
        max_value=600,
        step=10,
        default=120,
    ),
    # ICE state
    ConfigFieldSchema(
        key="ice_target_temp",
        name="Target Temperature",
        description="Target plate temperature for ice formation",
        type="float",
        category="ice",
        unit="°F",
        min_value=-20.0,
        max_value=20.0,
        step=0.5,
        default=-2.0,
    ),
    ConfigFieldSchema(
        key="ice_timeout",
        name="Timeout",
        description="Maximum time allowed for ice formation",
        type="int",
        category="ice",
        unit="seconds",
        min_value=300,
        max_value=3600,
        step=60,
        default=1500,
    ),
    # HEAT state (harvest)
    ConfigFieldSchema(
        key="harvest_threshold",
        name="Release Temperature",
        description="Plate temperature at which ice releases",
        type="float",
        category="harvest",
        unit="°F",
        min_value=30.0,
        max_value=60.0,
        step=0.5,
        default=38.0,
    ),
    ConfigFieldSchema(
        key="harvest_timeout",
        name="Timeout",
        description="Maximum time allowed for harvest phase",
        type="int",
        category="harvest",
        unit="seconds",
        min_value=60,
        max_value=600,
        step=10,
        default=240,
    ),
    ConfigFieldSchema(
        key="harvest_fill_time",
        name="Water Fill Time",
        description="Duration of water fill during harvest",
        type="int",
        category="harvest",
        unit="seconds",
        min_value=5,
        max_value=60,
        step=1,
        default=18,
    ),
    # CHILL state (rechill phase)
    ConfigFieldSchema(
        key="rechill_temp",
        name="Target Temperature",
        description="Target plate temperature after harvest",
        type="float",
        category="rechill",
        unit="°F",
        min_value=25.0,
        max_value=50.0,
        step=0.5,
        default=35.0,
    ),
    ConfigFieldSchema(
        key="rechill_timeout",
        name="Timeout",
        description="Maximum time allowed for rechill phase",
        type="int",
        category="rechill",
        unit="seconds",
        min_value=60,
        max_value=600,
        step=10,
        default=300,
    ),
    # IDLE state (bin full detection)
    ConfigFieldSchema(
        key="bin_full_threshold",
        name="Bin Full Temperature",
        description="Bin temperature indicating it is full of ice",
        type="float",
        category="idle",
        unit="°F",
        min_value=20.0,
        max_value=50.0,
        step=0.5,
        default=35.0,
    ),
    # STANDBY state
    ConfigFieldSchema(
        key="standby_timeout",
        name="Auto-Off Timeout",
        description="Time before auto-transitioning from STANDBY to OFF",
        type="float",
        category="standby",
        unit="seconds",
        min_value=60,
        max_value=7200,
        step=60,
        default=1200.0,
    ),
    # System settings (read-only)
    ConfigFieldSchema(
        key="poll_interval",
        name="Poll Interval",
        description="Interval between sensor readings",
        type="float",
        category="system",
        unit="seconds",
        default=5.0,
        readonly=True,
    ),
    ConfigFieldSchema(
        key="use_simulator",
        name="Simulator Mode",
        description="Whether running in simulation mode",
        type="bool",
        category="system",
        default=False,
        readonly=True,
    ),
]
