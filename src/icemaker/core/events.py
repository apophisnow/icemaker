"""Event system for icemaker state machine."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Optional


class EventType(Enum):
    """Types of events in the icemaker system."""

    # State machine events
    STATE_ENTER = auto()
    STATE_EXIT = auto()
    STATE_TIMEOUT = auto()

    # Temperature events
    TEMP_TARGET_REACHED = auto()
    TEMP_THRESHOLD_CROSSED = auto()
    TEMP_READING = auto()

    # Control events
    START_CYCLE = auto()
    STOP_CYCLE = auto()
    EMERGENCY_STOP = auto()

    # Hardware events
    RELAY_CHANGED = auto()
    SENSOR_ERROR = auto()

    # System events
    BIN_FULL = auto()
    BIN_NOT_FULL = auto()
    CYCLE_COMPLETE = auto()

    # Error events
    ERROR = auto()
    RECOVERED = auto()


@dataclass
class Event:
    """Event data structure for the event system.

    Events are emitted by the FSM and handlers, and can be consumed
    by listeners (e.g., WebSocket manager, logging, monitoring).

    Attributes:
        type: The type of event.
        timestamp: When the event occurred.
        data: Optional dictionary of event-specific data.
        source: Optional identifier for the event source.
    """

    type: EventType
    timestamp: datetime = field(default_factory=datetime.now)
    data: Optional[dict[str, Any]] = None
    source: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization.

        Returns:
            Dictionary representation of the event.
        """
        return {
            "type": self.type.name,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "source": self.source,
        }


def state_enter_event(
    state_name: str,
    from_state: Optional[str] = None,
) -> Event:
    """Create a STATE_ENTER event.

    Args:
        state_name: Name of the state being entered.
        from_state: Name of the previous state, if any.

    Returns:
        State enter event.
    """
    return Event(
        type=EventType.STATE_ENTER,
        data={"state": state_name, "from_state": from_state},
        source="fsm",
    )


def state_exit_event(state_name: str) -> Event:
    """Create a STATE_EXIT event.

    Args:
        state_name: Name of the state being exited.

    Returns:
        State exit event.
    """
    return Event(
        type=EventType.STATE_EXIT,
        data={"state": state_name},
        source="fsm",
    )


def temp_reading_event(
    plate_temp: float,
    bin_temp: float,
) -> Event:
    """Create a TEMP_READING event.

    Args:
        plate_temp: Current plate temperature in Fahrenheit.
        bin_temp: Current ice bin temperature in Fahrenheit.

    Returns:
        Temperature reading event.
    """
    return Event(
        type=EventType.TEMP_READING,
        data={"plate_temp": plate_temp, "bin_temp": bin_temp},
        source="sensors",
    )


def relay_changed_event(
    relay_name: str,
    new_state: bool,
) -> Event:
    """Create a RELAY_CHANGED event.

    Args:
        relay_name: Name of the relay that changed.
        new_state: New state of the relay (True=ON, False=OFF).

    Returns:
        Relay changed event.
    """
    return Event(
        type=EventType.RELAY_CHANGED,
        data={"relay": relay_name, "state": new_state},
        source="gpio",
    )


def error_event(
    message: str,
    error_type: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> Event:
    """Create an ERROR event.

    Args:
        message: Human-readable error message.
        error_type: Optional error classification.
        details: Optional additional error details.

    Returns:
        Error event.
    """
    data = {"message": message}
    if error_type:
        data["error_type"] = error_type
    if details:
        data["details"] = details
    return Event(
        type=EventType.ERROR,
        data=data,
        source="system",
    )
