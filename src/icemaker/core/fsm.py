"""Async finite state machine for icemaker control."""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Awaitable, Callable, Optional

from .events import Event, EventType, state_enter_event, state_exit_event
from .states import IcemakerState, TRANSITIONS, can_transition

logger = logging.getLogger(__name__)

# Type alias for state handler functions
StateHandler = Callable[["AsyncFSM", "FSMContext"], Awaitable[Optional[IcemakerState]]]

# Type alias for event listeners
EventListener = Callable[[Event], Awaitable[None]]


@dataclass
class FSMContext:
    """Runtime context for the FSM.

    Contains current sensor readings, timing information, and cycle statistics.
    Updated by the controller during operation.

    Attributes:
        plate_temp: Current plate temperature in Fahrenheit.
        bin_temp: Current ice bin temperature in Fahrenheit.
        target_temp: Current target temperature for the active state.
        cycle_count: Number of completed ice-making cycles.
        state_enter_time: When the current state was entered (wall clock).
        cycle_start_time: When the current cycle started.
        chill_mode: Current chill mode (PRECHILL or RECHILL).
        simulated_state_enter_time: Simulated time when state was entered.
    """

    plate_temp: float = 70.0
    bin_temp: float = 70.0
    target_temp: float = 32.0
    cycle_count: int = 0
    state_enter_time: datetime = field(default_factory=datetime.now)
    cycle_start_time: Optional[datetime] = None
    chill_mode: Optional[str] = None  # "prechill" or "rechill"
    simulated_state_enter_time: Optional[float] = None  # Simulated seconds at state entry


class AsyncFSM:
    """Async finite state machine for icemaker control.

    Manages state transitions, executes state handlers, and emits events.
    The FSM runs in an async loop, polling state handlers at a configurable
    interval.

    Example:
        fsm = AsyncFSM(initial_state=IcemakerState.OFF)
        fsm.register_handler(IcemakerState.OFF, off_handler)
        fsm.register_handler(IcemakerState.CHILL, chill_handler)
        await fsm.run()
    """

    def __init__(
        self,
        initial_state: IcemakerState = IcemakerState.OFF,
        poll_interval: float = 5.0,
    ) -> None:
        """Initialize the FSM.

        Args:
            initial_state: State to start in.
            poll_interval: Seconds between state handler polls (in simulated time when lockstep).
        """
        self._state = initial_state
        self._previous_state: Optional[IcemakerState] = None
        self._context = FSMContext()
        self._poll_interval = poll_interval
        self._running = False
        self._handlers: dict[IcemakerState, StateHandler] = {}
        self._listeners: list[EventListener] = []
        self._state_changed = asyncio.Event()
        self._simulated_time_getter: Optional[Callable[[], float]] = None
        self._last_poll_simulated_time: float = 0.0

    def set_simulated_time_getter(self, getter: Callable[[], float]) -> None:
        """Set a function to get current simulated time.

        When set, time_in_state() will use simulated time instead of wall clock.

        Args:
            getter: Function that returns current simulated time in seconds.
        """
        self._simulated_time_getter = getter

    @property
    def state(self) -> IcemakerState:
        """Current FSM state."""
        return self._state

    @property
    def previous_state(self) -> Optional[IcemakerState]:
        """Previous FSM state, or None if this is the initial state."""
        return self._previous_state

    @property
    def context(self) -> FSMContext:
        """FSM runtime context."""
        return self._context

    @property
    def is_running(self) -> bool:
        """Whether the FSM main loop is running."""
        return self._running

    def register_handler(
        self,
        state: IcemakerState,
        handler: StateHandler,
    ) -> None:
        """Register an async handler for a state.

        The handler is called each poll interval while in the state.
        It should return the next state to transition to, or None
        to stay in the current state.

        Args:
            state: State to register handler for.
            handler: Async function taking (fsm, context) -> Optional[State].
        """
        self._handlers[state] = handler
        logger.debug("Registered handler for state %s", state.name)

    def add_listener(self, listener: EventListener) -> None:
        """Add event listener for state changes and other events.

        Args:
            listener: Async function taking Event.
        """
        self._listeners.append(listener)

    def remove_listener(self, listener: EventListener) -> None:
        """Remove an event listener.

        Args:
            listener: Previously added listener function.
        """
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def _emit_event(self, event: Event) -> None:
        """Emit event to all listeners.

        Args:
            event: Event to emit.
        """
        for listener in self._listeners:
            try:
                await listener(event)
            except Exception as e:
                logger.error("Event listener error: %s", e)

    async def transition_to(self, new_state: IcemakerState) -> bool:
        """Attempt to transition to a new state.

        Validates the transition against the state transition table,
        emits state exit/enter events, and updates the FSM state.

        Args:
            new_state: Target state to transition to.

        Returns:
            True if transition succeeded, False if invalid.
        """
        if not can_transition(self._state, new_state):
            logger.warning(
                "Invalid transition: %s -> %s",
                self._state.name,
                new_state.name,
            )
            return False

        # Exit current state
        await self._emit_event(state_exit_event(self._state.name))

        # Update state
        self._previous_state = self._state
        self._state = new_state
        self._context.state_enter_time = datetime.now()
        # Record simulated time at state entry if available
        if self._simulated_time_getter is not None:
            self._context.simulated_state_enter_time = self._simulated_time_getter()

        # Enter new state
        await self._emit_event(
            state_enter_event(new_state.name, self._previous_state.name)
        )

        self._state_changed.set()
        logger.info("State transition: %s -> %s", self._previous_state.name, new_state.name)
        return True

    def time_in_state(self) -> float:
        """Get seconds elapsed in current state.

        Uses simulated time if available, otherwise wall clock time.

        Returns:
            Seconds since entering current state.
        """
        if (
            self._simulated_time_getter is not None
            and self._context.simulated_state_enter_time is not None
        ):
            return self._simulated_time_getter() - self._context.simulated_state_enter_time
        return (datetime.now() - self._context.state_enter_time).total_seconds()

    async def wait_for_state_change(self, timeout: Optional[float] = None) -> bool:
        """Wait for a state change to occur.

        Args:
            timeout: Maximum seconds to wait, or None for no timeout.

        Returns:
            True if state changed, False if timeout occurred.
        """
        self._state_changed.clear()
        try:
            await asyncio.wait_for(
                self._state_changed.wait(),
                timeout=timeout,
            )
            return True
        except asyncio.TimeoutError:
            return False

    async def run(self) -> None:
        """Main FSM loop.

        Continuously polls state handlers and processes transitions
        until stop() is called.

        When a simulated time getter is configured, the FSM runs in lockstep
        with the simulation - it waits for simulated time to advance by
        poll_interval before executing the next handler.
        """
        self._running = True
        logger.info("FSM started in state: %s", self._state.name)

        # Initialize last poll time
        if self._simulated_time_getter is not None:
            self._last_poll_simulated_time = self._simulated_time_getter()

        # Emit initial state enter event
        await self._emit_event(state_enter_event(self._state.name))

        while self._running:
            handler = self._handlers.get(self._state)

            if handler:
                try:
                    # Check for timeout
                    config = TRANSITIONS.get(self._state)
                    if config:
                        elapsed = self.time_in_state()
                        if elapsed > config.timeout_seconds:
                            await self._emit_event(Event(
                                type=EventType.STATE_TIMEOUT,
                                data={
                                    "state": self._state.name,
                                    "elapsed": elapsed,
                                    "timeout": config.timeout_seconds,
                                },
                                source="fsm",
                            ))

                    # Execute state handler
                    next_state = await handler(self, self._context)

                    # Transition if handler returns new state
                    if next_state is not None and next_state != self._state:
                        await self.transition_to(next_state)

                    # Wait for next poll interval
                    await self._wait_for_next_poll()

                except asyncio.CancelledError:
                    logger.info("FSM task cancelled")
                    break
                except Exception as e:
                    logger.error("Handler error in %s: %s", self._state.name, e)
                    await self._emit_event(Event(
                        type=EventType.ERROR,
                        data={
                            "state": self._state.name,
                            "error": str(e),
                        },
                        source="fsm",
                    ))
                    # Transition to ERROR state
                    if can_transition(self._state, IcemakerState.ERROR):
                        await self.transition_to(IcemakerState.ERROR)
            else:
                # No handler for this state, just wait
                try:
                    await self._wait_for_next_poll()
                except asyncio.CancelledError:
                    logger.info("FSM task cancelled during sleep")
                    break

        logger.info("FSM stopped")

    async def _wait_for_next_poll(self) -> None:
        """Wait until the next poll interval.

        In lockstep mode (with simulated time), waits for simulated time
        to advance by poll_interval. Otherwise uses wall-clock sleep.
        """
        if self._simulated_time_getter is not None:
            # Lockstep mode: wait for simulated time to advance
            target_time = self._last_poll_simulated_time + self._poll_interval
            while self._running:
                current_sim_time = self._simulated_time_getter()
                if current_sim_time >= target_time:
                    self._last_poll_simulated_time = current_sim_time
                    break
                # Brief sleep to allow simulation to advance
                await asyncio.sleep(0.01)
        else:
            # Wall-clock mode
            await asyncio.sleep(self._poll_interval)

    async def stop(self) -> None:
        """Stop the FSM.

        Transitions to SHUTDOWN state and stops the main loop.
        """
        self._running = False
        if can_transition(self._state, IcemakerState.SHUTDOWN):
            await self.transition_to(IcemakerState.SHUTDOWN)
