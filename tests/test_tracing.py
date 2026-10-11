from ledger.tracing import initialize_tracing


def test_tracing_is_disabled_without_a_project_key():
    assert initialize_tracing(None) is False

