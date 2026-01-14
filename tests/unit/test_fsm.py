"""Tests for async FSM."""

import pytest

from icemaker.core.events import EventType
from icemaker.core.fsm import AsyncFSM
from icemaker.core.states import IcemakerState


class TestFSMInitialization:
    """Test FSM initialization."""

    def test_initial_state_is_idle(self, fsm: AsyncFSM) -> None:
        """FSM should start in IDLE state."""
        assert fsm.state == IcemakerState.IDLE

    def test_initial_state_can_be_configured(self) -> None:
        """FSM should accept initial state parameter."""
        fsm = AsyncFSM(initial_state=IcemakerState.CHILL)
        assert fsm.state == IcemakerState.CHILL

    def test_previous_state_is_none_initially(self, fsm: AsyncFSM) -> None:
        """Previous state should be None initially."""
        assert fsm.previous_state is None

    def test_is_not_running_initially(self, fsm: AsyncFSM) -> None:
        """FSM should not be running initially."""
        assert not fsm.is_running


class TestFSMTransitions:
    """Test FSM state transitions."""

    @pytest.mark.asyncio
    async def test_valid_transition_idle_to_chill(self, fsm: AsyncFSM) -> None:
        """Should allow transition from IDLE to CHILL."""
        success = await fsm.transition_to(IcemakerState.CHILL)
        assert success
        assert fsm.state == IcemakerState.CHILL

    @pytest.mark.asyncio
    async def test_valid_transition_chill_to_ice(self, fsm: AsyncFSM) -> None:
        """Should allow transition from CHILL to ICE."""
        await fsm.transition_to(IcemakerState.CHILL)
        success = await fsm.transition_to(IcemakerState.ICE)
        assert success
        assert fsm.state == IcemakerState.ICE

    @pytest.mark.asyncio
    async def test_invalid_transition_idle_to_ice(self, fsm: AsyncFSM) -> None:
        """Should reject direct transition from IDLE to ICE."""
        success = await fsm.transition_to(IcemakerState.ICE)
        assert not success
        assert fsm.state == IcemakerState.IDLE

    @pytest.mark.asyncio
    async def test_invalid_transition_ice_to_idle(self, fsm: AsyncFSM) -> None:
        """Should reject direct transition from ICE to IDLE."""
        await fsm.transition_to(IcemakerState.CHILL)
        await fsm.transition_to(IcemakerState.ICE)
        success = await fsm.transition_to(IcemakerState.IDLE)
        assert not success
        assert fsm.state == IcemakerState.ICE

    @pytest.mark.asyncio
    async def test_previous_state_updated(self, fsm: AsyncFSM) -> None:
        """Previous state should be updated after transition."""
        await fsm.transition_to(IcemakerState.CHILL)
        assert fsm.previous_state == IcemakerState.IDLE

        await fsm.transition_to(IcemakerState.ICE)
        assert fsm.previous_state == IcemakerState.CHILL

    @pytest.mark.asyncio
    async def test_full_cycle_transition_path(self, fsm: AsyncFSM) -> None:
        """Should complete full IDLE->CHILL->ICE->HEAT->CHILL cycle."""
        # IDLE -> CHILL
        assert await fsm.transition_to(IcemakerState.CHILL)
        assert fsm.state == IcemakerState.CHILL

        # CHILL -> ICE
        assert await fsm.transition_to(IcemakerState.ICE)
        assert fsm.state == IcemakerState.ICE

        # ICE -> HEAT
        assert await fsm.transition_to(IcemakerState.HEAT)
        assert fsm.state == IcemakerState.HEAT

        # HEAT -> CHILL (rechill)
        assert await fsm.transition_to(IcemakerState.CHILL)
        assert fsm.state == IcemakerState.CHILL

    @pytest.mark.asyncio
    async def test_error_transition_from_operating_state(self, fsm: AsyncFSM) -> None:
        """ERROR state should be reachable from operating states."""
        await fsm.transition_to(IcemakerState.CHILL)
        await fsm.transition_to(IcemakerState.ICE)

        success = await fsm.transition_to(IcemakerState.ERROR)
        assert success
        assert fsm.state == IcemakerState.ERROR


class TestFSMEvents:
    """Test FSM event emission."""

    @pytest.mark.asyncio
    async def test_state_enter_event_emitted(self, fsm: AsyncFSM) -> None:
        """STATE_ENTER event should be emitted on transition."""
        events: list = []

        async def listener(event):
            events.append(event)

        fsm.add_listener(listener)
        await fsm.transition_to(IcemakerState.CHILL)

        enter_events = [e for e in events if e.type == EventType.STATE_ENTER]
        assert len(enter_events) == 1
        assert enter_events[0].data["state"] == "CHILL"

    @pytest.mark.asyncio
    async def test_state_exit_event_emitted(self, fsm: AsyncFSM) -> None:
        """STATE_EXIT event should be emitted on transition."""
        events: list = []

        async def listener(event):
            events.append(event)

        fsm.add_listener(listener)
        await fsm.transition_to(IcemakerState.CHILL)

        exit_events = [e for e in events if e.type == EventType.STATE_EXIT]
        assert len(exit_events) == 1
        assert exit_events[0].data["state"] == "IDLE"

    @pytest.mark.asyncio
    async def test_listener_can_be_removed(self, fsm: AsyncFSM) -> None:
        """Removed listener should not receive events."""
        events: list = []

        async def listener(event):
            events.append(event)

        fsm.add_listener(listener)
        fsm.remove_listener(listener)
        await fsm.transition_to(IcemakerState.CHILL)

        assert len(events) == 0


class TestFSMContext:
    """Test FSM context management."""

    def test_context_has_initial_values(self, fsm: AsyncFSM) -> None:
        """Context should have sensible initial values."""
        ctx = fsm.context
        assert ctx.plate_temp == 70.0
        assert ctx.bin_temp == 70.0
        assert ctx.cycle_count == 0

    @pytest.mark.asyncio
    async def test_state_enter_time_updated(self, fsm: AsyncFSM) -> None:
        """State enter time should update on transition."""
        initial_time = fsm.context.state_enter_time
        await fsm.transition_to(IcemakerState.CHILL)
        assert fsm.context.state_enter_time > initial_time

    def test_time_in_state(self, fsm: AsyncFSM) -> None:
        """time_in_state should return elapsed seconds."""
        time_elapsed = fsm.time_in_state()
        assert time_elapsed >= 0
