import neatlogs
from neatlogs._wrap_utils import active_neatlogs_context
from opentelemetry import trace as otel_trace


def current_trace_id() -> str | None:
    active_context = active_neatlogs_context()
    span = (
        otel_trace.get_current_span(active_context)
        if active_context
        else otel_trace.get_current_span()
    )
    context = span.get_span_context()
    if not context.is_valid:
        return None
    return f"{context.trace_id:032x}"


def initialize_tracing(api_key: str | None) -> bool:
    if not api_key:
        return False
    neatlogs.init(
        api_key=api_key,
        workflow_name="promise-ledger",
        tags=["neathack", "el-el-ems"],
        capture_logs=True,
    )
    return True


def finish_tracing(enabled: bool) -> None:
    if enabled:
        neatlogs.flush()
        neatlogs.shutdown()
