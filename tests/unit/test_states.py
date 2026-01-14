"""Tests for state enum and transitions."""

import pytest

from icemaker.core.states import (
    IcemakerState,
    TRANSITIONS,
    can_transition,
    get_allowed_transitions,
)


class TestStateTransitions:
    """Test state transition validation."""

    def test_idle_can_transition_to_chill(self) -> None:
        """IDLE -> CHILL should be valid."""
        assert can_transition(IcemakerState.IDLE, IcemakerState.CHILL)

    def test_idle_can_transition_to_power_on(self) -> None:
        """IDLE -> POWER_ON should be valid."""
        assert can_transition(IcemakerState.IDLE, IcemakerState.POWER_ON)

    def test_idle_can_transition_to_shutdown(self) -> None:
        """IDLE -> SHUTDOWN should be valid."""
        assert can_transition(IcemakerState.IDLE, IcemakerState.SHUTDOWN)

    def test_idle_cannot_transition_to_ice(self) -> None:
        """IDLE -> ICE should be invalid (must go through CHILL)."""
        assert not can_transition(IcemakerState.IDLE, IcemakerState.ICE)

    def test_idle_cannot_transition_to_heat(self) -> None:
        """IDLE -> HEAT should be invalid."""
        assert not can_transition(IcemakerState.IDLE, IcemakerState.HEAT)

    def test_chill_can_transition_to_ice(self) -> None:
        """CHILL -> ICE should be valid."""
        assert can_transition(IcemakerState.CHILL, IcemakerState.ICE)

    def test_chill_can_transition_to_idle(self) -> None:
        """CHILL -> IDLE should be valid (for rechill -> bin full)."""
        assert can_transition(IcemakerState.CHILL, IcemakerState.IDLE)

    def test_chill_can_transition_to_error(self) -> None:
        """CHILL -> ERROR should be valid."""
        assert can_transition(IcemakerState.CHILL, IcemakerState.ERROR)

    def test_ice_can_transition_to_heat(self) -> None:
        """ICE -> HEAT should be valid."""
        assert can_transition(IcemakerState.ICE, IcemakerState.HEAT)

    def test_ice_cannot_transition_to_idle(self) -> None:
        """ICE -> IDLE should be invalid (must harvest first)."""
        assert not can_transition(IcemakerState.ICE, IcemakerState.IDLE)

    def test_heat_can_transition_to_chill(self) -> None:
        """HEAT -> CHILL should be valid (rechill)."""
        assert can_transition(IcemakerState.HEAT, IcemakerState.CHILL)

    def test_heat_cannot_transition_to_idle(self) -> None:
        """HEAT -> IDLE should be invalid (must rechill)."""
        assert not can_transition(IcemakerState.HEAT, IcemakerState.IDLE)

    def test_error_can_transition_to_idle(self) -> None:
        """ERROR -> IDLE should be valid (recovery)."""
        assert can_transition(IcemakerState.ERROR, IcemakerState.IDLE)

    def test_error_can_transition_to_shutdown(self) -> None:
        """ERROR -> SHUTDOWN should be valid."""
        assert can_transition(IcemakerState.ERROR, IcemakerState.SHUTDOWN)

    def test_shutdown_can_transition_to_idle(self) -> None:
        """SHUTDOWN -> IDLE should be valid."""
        assert can_transition(IcemakerState.SHUTDOWN, IcemakerState.IDLE)


class TestGetAllowedTransitions:
    """Test get_allowed_transitions function."""

    def test_idle_allowed_transitions(self) -> None:
        """IDLE should allow POWER_ON, CHILL, SHUTDOWN."""
        allowed = get_allowed_transitions(IcemakerState.IDLE)
        assert IcemakerState.POWER_ON in allowed
        assert IcemakerState.CHILL in allowed
        assert IcemakerState.SHUTDOWN in allowed
        assert IcemakerState.ICE not in allowed

    def test_chill_allowed_transitions(self) -> None:
        """CHILL should allow ICE, IDLE, ERROR, SHUTDOWN."""
        allowed = get_allowed_transitions(IcemakerState.CHILL)
        assert IcemakerState.ICE in allowed
        assert IcemakerState.IDLE in allowed
        assert IcemakerState.ERROR in allowed
        assert IcemakerState.SHUTDOWN in allowed

    def test_ice_allowed_transitions(self) -> None:
        """ICE should allow HEAT, ERROR, SHUTDOWN."""
        allowed = get_allowed_transitions(IcemakerState.ICE)
        assert IcemakerState.HEAT in allowed
        assert IcemakerState.ERROR in allowed
        assert IcemakerState.SHUTDOWN in allowed
        assert IcemakerState.IDLE not in allowed


class TestTransitionsTable:
    """Test TRANSITIONS table is properly configured."""

    def test_all_states_have_transitions(self) -> None:
        """Every state should have an entry in TRANSITIONS."""
        for state in IcemakerState:
            assert state in TRANSITIONS, f"Missing transition config for {state}"

    def test_all_states_have_timeout(self) -> None:
        """Every state should have a timeout configured."""
        for state, config in TRANSITIONS.items():
            assert config.timeout_seconds > 0, f"{state} has invalid timeout"

    def test_error_and_idle_have_infinite_timeout(self) -> None:
        """ERROR and IDLE should have infinite timeouts."""
        assert TRANSITIONS[IcemakerState.IDLE].timeout_seconds == float("inf")
        assert TRANSITIONS[IcemakerState.ERROR].timeout_seconds == float("inf")
