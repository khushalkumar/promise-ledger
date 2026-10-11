from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Column, delete
from sqlmodel import Field, Session, SQLModel, create_engine, select

from ledger.models import WorkflowEvent, WorkflowRun, WorkflowStage


class RunRow(SQLModel, table=True):
    id: str = Field(primary_key=True)
    target_repository: str
    stage: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunEventRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="runrow.id")
    stage: str
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProbeDependencyRow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    run_id: str = Field(index=True, foreign_key="runrow.id")
    probe_id: str = Field(index=True)
    dependency: str = Field(index=True)


class RunStore:
    def __init__(self, database_url: str) -> None:
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, connect_args=connect_args)
        SQLModel.metadata.create_all(self.engine)

    def create_run(self, run_id: str, *, target_repository: str) -> WorkflowRun:
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            if session.get(RunRow, run_id) is not None:
                raise ValueError(f"run already exists: {run_id}")
            session.add(
                RunRow(
                    id=run_id,
                    target_repository=target_repository,
                    stage=WorkflowStage.CREATED.value,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.add(
                RunEventRow(
                    run_id=run_id,
                    stage=WorkflowStage.CREATED.value,
                    payload={},
                    created_at=now,
                )
            )
            session.commit()
        created = self.get_run(run_id)
        if created is None:  # pragma: no cover - defensive database boundary
            raise RuntimeError(f"failed to create run: {run_id}")
        return created

    def record_stage(
        self,
        run_id: str,
        stage: WorkflowStage,
        payload: dict[str, object] | None = None,
    ) -> None:
        now = datetime.now(UTC)
        with Session(self.engine) as session:
            run = session.get(RunRow, run_id)
            if run is None:
                raise KeyError(run_id)
            run.stage = stage.value
            run.updated_at = now
            session.add(run)
            session.add(
                RunEventRow(
                    run_id=run_id,
                    stage=stage.value,
                    payload=payload or {},
                    created_at=now,
                )
            )
            session.commit()

    def get_run(self, run_id: str) -> WorkflowRun | None:
        with Session(self.engine) as session:
            run = session.get(RunRow, run_id)
            if run is None:
                return None
            rows = session.exec(
                select(RunEventRow)
                .where(RunEventRow.run_id == run_id)
                .order_by(RunEventRow.id)
            ).all()
            return WorkflowRun(
                id=run.id,
                target_repository=run.target_repository,
                stage=WorkflowStage(run.stage),
                events=[
                    WorkflowEvent(
                        stage=WorkflowStage(row.stage),
                        payload=row.payload,
                        created_at=row.created_at,
                    )
                    for row in rows
                ],
            )

    def replace_probe_dependencies(
        self, run_id: str, dependencies: dict[str, list[str]]
    ) -> None:
        with Session(self.engine) as session:
            if session.get(RunRow, run_id) is None:
                raise KeyError(run_id)
            session.exec(delete(ProbeDependencyRow).where(ProbeDependencyRow.run_id == run_id))
            for probe_id, values in dependencies.items():
                for dependency in sorted(set(values)):
                    session.add(
                        ProbeDependencyRow(
                            run_id=run_id,
                            probe_id=probe_id,
                            dependency=dependency,
                        )
                    )
            session.commit()

    def affected_probe_ids(self, run_id: str, changed_dependencies: list[str]) -> list[str]:
        if not changed_dependencies:
            return []
        with Session(self.engine) as session:
            rows = session.exec(
                select(ProbeDependencyRow.probe_id).where(
                    ProbeDependencyRow.run_id == run_id,
                    ProbeDependencyRow.dependency.in_(changed_dependencies),
                )
            ).all()
        return sorted(set(rows))
