import neatlogs


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
