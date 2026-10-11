from ledger import tracing


class FakeContext:
    is_valid = True
    trace_id = 0xABC


class FakeSpan:
    def get_span_context(self):
        return FakeContext()


def test_tracing_is_disabled_without_a_project_key():
    assert tracing.initialize_tracing(None) is False


def test_current_trace_id_uses_neatlogs_private_context(monkeypatch):
    private_context = object()
    monkeypatch.setattr(tracing, "active_neatlogs_context", lambda: private_context)
    monkeypatch.setattr(
        tracing.otel_trace,
        "get_current_span",
        lambda context=None: FakeSpan() if context is private_context else None,
    )

    assert tracing.current_trace_id() == "00000000000000000000000000000abc"
