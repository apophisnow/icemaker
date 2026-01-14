"""State definitions and transition rules for icemaker FSM."""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class IcemakerState(Enum):
    """Icemaker operational states.

    States follow the ice-making cycle:
    IDLE -> POWER_ON -> CHILL (prechill) -> ICE -> HEAT -> CHILL (rechill) -> ...

    The cycle repeats until the bin is full, at which point the system
    enters IDLE state until the bin has room for more ice.
    """

    IDLE = auto()
    POWER_ON = auto()
    CHILL = auto()
    ICE = auto()
    HEAT = auto()
    ERROR = auto()
    SHUTDOWN = auto()


class ChillMode(Enum):
    """Sub-modes for the CHILL state.

    PRECHILL: Initial cooling before ice making (target: 32°F)
    RECHILL: Cooling after harvest before next cycle (target: 35°F)
    """

    PRECHILL = auto()
    RECHILL = auto()


@dataclass(frozen=True)
class StateConfig:
    """Configuration for a specific state.

    Attributes:
        target_temp: Target temperature in Fahrenheit, or None if N/A.
        timeout_seconds: Maximum time allowed in state before timeout.
        allowed_transitions: Set of states that can be transitioned to.
    """

    target_temp: Optional[float]
    timeout_seconds: float
    allowed_transitions: frozenset[IcemakerState]


# State transition table defining valid transitions and state configurations
TRANSITIONS: dict[IcemakerState, StateConfig] = {
    IcemakerState.IDLE: StateConfig(
        target_temp=None,
        timeout_seconds=float("inf"),
        allowed_transitions=frozenset({
            IcemakerState.POWER_ON,
            IcemakerState.CHILL,
            IcemakerState.SHUTDOWN,
        }),
    ),
    IcemakerState.POWER_ON: StateConfig(
        target_temp=None,
        timeout_seconds=120,  # 2 minutes for startup sequence
        allowed_transitions=frozenset({
            IcemakerState.CHILL,
            IcemakerState.ERROR,
            IcemakerState.SHUTDOWN,
        }),
    ),
    IcemakerState.CHILL: StateConfig(
        target_temp=32.0,  # Default, overridden by chill mode
        timeout_seconds=300,  # 5 minutes default
        allowed_transitions=frozenset({
            IcemakerState.ICE,
            IcemakerState.IDLE,
            IcemakerState.ERROR,
            IcemakerState.SHUTDOWN,
        }),
    ),
    IcemakerState.ICE: StateConfig(
        target_temp=-2.0,
        timeout_seconds=1500,  # 25 minutes
        allowed_transitions=frozenset({
            IcemakerState.HEAT,
            IcemakerState.ERROR,
            IcemakerState.SHUTDOWN,
        }),
    ),
    IcemakerState.HEAT: StateConfig(
        target_temp=38.0,
        timeout_seconds=240,  # 4 minutes
        allowed_transitions=frozenset({
            IcemakerState.CHILL,
            IcemakerState.ERROR,
            IcemakerState.SHUTDOWN,
        }),
    ),
    IcemakerState.ERROR: StateConfig(
        target_temp=None,
        timeout_seconds=float("inf"),
        allowed_transitions=frozenset({
            IcemakerState.IDLE,
            IcemakerState.SHUTDOWN,
        }),
    ),
    IcemakerState.SHUTDOWN: StateConfig(
        target_temp=None,
        timeout_seconds=30,
        allowed_transitions=frozenset({
            IcemakerState.IDLE,
        }),
    ),
}


def can_transition(from_state: IcemakerState, to_state: IcemakerState) -> bool:
    """Check if a state transition is valid.

    Args:
        from_state: Current state.
        to_state: Desired target state.

    Returns:
        True if the transition is allowed, False otherwise.
    """
    config = TRANSITIONS.get(from_state)
    if config is None:
        return False
    return to_state in config.allowed_transitions


def get_allowed_transitions(state: IcemakerState) -> frozenset[IcemakerState]:
    """Get the set of states that can be transitioned to from the given state.

    Args:
        state: Current state.

    Returns:
        Set of allowed target states.
    """
    config = TRANSITIONS.get(state)
    if config is None:
        return frozenset()
    return config.allowed_transitions
