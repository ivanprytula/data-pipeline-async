"""Re-export shim — implementation lives in libs.platform.circuit_breaker."""

from libs.platform.circuit_breaker import *  # noqa: F401, F403
from libs.platform.circuit_breaker import (
    CircuitOpenError,
    CircuitState,
    _CircuitBreaker,
    circuit_breaker,
)


__all__ = ["CircuitState", "CircuitOpenError", "_CircuitBreaker", "circuit_breaker"]
