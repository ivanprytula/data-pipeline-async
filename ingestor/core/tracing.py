"""Re-export shim — implementation lives in libs.platform.tracing."""

from libs.platform.tracing import *  # noqa: F401, F403
from libs.platform.tracing import get_trace_id, setup_tracing


__all__ = ["setup_tracing", "get_trace_id"]
