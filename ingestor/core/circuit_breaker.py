"""Circuit breaker decorator for async functions.

States (classic three-state machine):

    CLOSED ──(failures >= threshold)──► OPEN
      ▲                                   │
      │                                   │ (recovery_timeout elapsed)
      │                                 HALF_OPEN
      │                                   │
      └────────(next call succeeds)───────┘

- CLOSED:    Normal operation. Failures are counted.
- OPEN:      Calls rejected immediately (CircuitOpenError). Protects the
             downstream from a flood of retries while it recovers.
- HALF_OPEN: One probe call is allowed. Success → CLOSED. Failure → OPEN.

Advanced Python here:
- asyncio.Lock for race-free state transitions in async coroutine context
- Decorator factory: @circuit_breaker(failure_threshold=5, recovery_timeout=30)
- ContextVar: trace_id propagation is handled by the caller (Phase 4 spec)
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from enum import Enum, auto
from typing import Any


try:
    from ingestor.metrics import circuit_breaker_state

    _METRICS_AVAILABLE = True
except ImportError:
    _METRICS_AVAILABLE = False


logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitOpenError(Exception):
    """Raised when a guarded call is attempted while the circuit is OPEN."""


class _CircuitBreaker:
    """Stateful circuit breaker bound to one decorated function.

    Not intended for direct use — see the `circuit_breaker` decorator factory.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int,
        recovery_timeout: float,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float | None = None
        # Lock created lazily so it binds to the running event loop
        self._lock: asyncio.Lock | None = None

    @property
    def state(self) -> CircuitState:
        return self._state

    def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _maybe_transition_to_half_open(self) -> None:
        if self._state == CircuitState.OPEN:
            elapsed = time.monotonic() - (self._last_failure_time or 0.0)
            if elapsed >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info(
                    "circuit_half_open",
                    extra={"circuit": self.name, "after_seconds": round(elapsed, 1)},
                )
                if _METRICS_AVAILABLE:
                    circuit_breaker_state.labels(circuit=self.name).set(2)

    def _on_success(self) -> None:
        if self._state != CircuitState.CLOSED:
            logger.info("circuit_closed", extra={"circuit": self.name})
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        if _METRICS_AVAILABLE:
            circuit_breaker_state.labels(circuit=self.name).set(0)

    def _on_failure(self) -> None:
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if (
            self._failure_count >= self.failure_threshold
            or self._state == CircuitState.HALF_OPEN
        ):
            prev = self._state
            self._state = CircuitState.OPEN
            if prev != CircuitState.OPEN:
                logger.warning(
                    "circuit_opened",
                    extra={"circuit": self.name, "failures": self._failure_count},
                )
            if _METRICS_AVAILABLE:
                circuit_breaker_state.labels(circuit=self.name).set(1)

    async def call(self, func: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute func through the circuit breaker gate.

        Args:
            func: The coroutine function to call.
            *args: Positional arguments forwarded to func.
            **kwargs: Keyword arguments forwarded to func.

        Returns:
            Whatever func returns on success.

        Raises:
            CircuitOpenError: When the circuit is OPEN and the probe window has
                              not yet elapsed.
            Exception: Re-raises any exception raised by func (after recording
                       the failure).
        """
        lock = self._get_lock()
        async with lock:
            self._maybe_transition_to_half_open()
            if self._state == CircuitState.OPEN:
                raise CircuitOpenError(
                    f"Circuit '{self.name}' is OPEN — call rejected to protect downstream"
                )

        try:
            result = await func(*args, **kwargs)
        except Exception:
            async with lock:
                self._on_failure()
            raise
        else:
            async with lock:
                self._on_success()
            return result


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: float = 30.0,
) -> Callable:
    """Decorator factory that wraps an async function with a circuit breaker.

    Args:
        failure_threshold: Consecutive failures before opening the circuit.
        recovery_timeout: Seconds in OPEN state before transitioning to HALF_OPEN.

    Returns:
        Decorator that wraps the target coroutine function.

    Example:
        @circuit_breaker(failure_threshold=5, recovery_timeout=30)
        async def call_external_service(payload: dict) -> None:
            ...  # any exception here is counted as a failure

    Raises:
        CircuitOpenError: When the circuit is OPEN and a call is attempted.
    """

    def decorator(func: Callable) -> Callable:
        breaker = _CircuitBreaker(
            name=func.__qualname__,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await breaker.call(func, *args, **kwargs)

        # Expose the breaker instance for inspection / testing
        wrapper._circuit_breaker = breaker  # type: ignore[attr-defined]
        return wrapper

    return decorator
