from __future__ import annotations

import re
from collections.abc import Sequence
from itertools import combinations

import neatlogs

from ledger.models import Promise, PromiseConflict, PromiseKind, Verdict

RETENTION_KINDS = {PromiseKind.DELETION_DEADLINE, PromiseKind.RETENTION_LIMIT}
IGNORED_WORDS = {"and", "for", "of", "the", "within"}


@neatlogs.span(kind="GUARDRAIL", name="promise_conflict_detector")
def detect_conflicts(promises: Sequence[Promise]) -> list[PromiseConflict]:
    conflicts: list[PromiseConflict] = []
    candidates = [
        promise
        for promise in promises
        if promise.kind in RETENTION_KINDS and promise.deadline_days is not None
    ]
    for left, right in combinations(candidates, 2):
        if left.source.document == right.source.document:
            continue
        if left.deadline_days == right.deadline_days:
            continue
        if len(_subject_terms(left) & _subject_terms(right)) < 2:
            continue
        stricter, looser = sorted(
            (left, right),
            key=lambda item: int(item.deadline_days or 0),
        )
        conflict_number = len(conflicts) + 3
        conflicts.append(
            PromiseConflict(
                id=f"C-{conflict_number:03d}",
                promise_ids=sorted([left.id, right.id]),
                verdict=Verdict.VIOLATED,
                detail=(
                    f"{stricter.source.document} limits overlapping data to "
                    f"{stricter.deadline_days} days, but {looser.source.document} allows "
                    f"{looser.deadline_days} days"
                ),
            )
        )
    return conflicts


def _subject_terms(promise: Promise) -> set[str]:
    text = " ".join([promise.object, *promise.includes]).lower()
    return {
        word
        for word in re.findall(r"[a-z0-9]+", text)
        if len(word) > 2 and word not in IGNORED_WORDS
    }
