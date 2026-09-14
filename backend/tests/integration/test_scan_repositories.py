"""Scan repository round trips and database-backed concurrency constraints."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nostalgiabox.application.scans import ScanAlreadyRunningError
from nostalgiabox.domain import (
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    ScanCounters,
    ScanIssue,
    ScanIssueId,
    ScanIssueSeverity,
    ScanKind,
    ScanRun,
    ScanRunId,
    ScanStatus,
)
from nostalgiabox.persistence.catalogue_repositories import SqlAlchemyMediaSourceRepository
from nostalgiabox.persistence.scan_repositories import (
    SqlAlchemyScanIssueRepository,
    SqlAlchemyScanRunRepository,
)

_NOW = datetime(2026, 8, 10, 12, tzinfo=UTC)


def test_scan_run_and_issue_repositories_round_trip_without_committing(
    persistence_session: Session,
) -> None:
    _store_source(persistence_session)
    run = _queued_run("run-1")
    runs = SqlAlchemyScanRunRepository(persistence_session)
    issues = SqlAlchemyScanIssueRepository(persistence_session)
    runs.add(run)
    issue = ScanIssue(
        ScanIssueId("issue-1"),
        run.id,
        "key",
        "scan.interrupted",
        "Safe issue.",
        _NOW,
        ScanIssueSeverity.WARNING,
    )
    assert issues.add(issue)
    assert not issues.add(issue)
    runs.update(replace(run, counters=ScanCounters(issues=1)))
    persistence_session.flush()

    assert runs.get(run.id) is not None
    assert runs.next_generation(run.source_id) == 2
    assert runs.has_active(run.source_id)
    assert issues.list_for_run(run.id) == (issue,)


@pytest.mark.parametrize(
    ("kind", "status", "generation", "discovered", "added", "error_code", "error_message"),
    [
        ("invalid", "queued", 1, 0, 0, None, None),
        ("full", "invalid", 1, 0, 0, None, None),
        ("full", "queued", 0, 0, 0, None, None),
        ("full", "queued", 1, -1, 0, None, None),
        ("full", "queued", 1, 0, 1, None, None),
        ("full", "queued", 1, 0, 0, "scan.failed", None),
    ],
)
def test_database_rejects_invalid_scan_run_values(
    persistence_session: Session,
    kind: str,
    status: str,
    generation: int,
    discovered: int,
    added: int,
    error_code: str | None,
    error_message: str | None,
) -> None:
    _store_source(persistence_session)

    with pytest.raises(IntegrityError):
        _insert_run(
            persistence_session,
            "invalid-run",
            kind=kind,
            status=status,
            generation=generation,
            discovered=discovered,
            added=added,
            error_code=error_code,
            error_message=error_message,
        )


def test_database_enforces_one_active_run_per_source(
    persistence_session: Session,
) -> None:
    _store_source(persistence_session)
    _insert_run(persistence_session, "run-1", generation=1)

    with pytest.raises(IntegrityError):
        _insert_run(persistence_session, "run-2", generation=2)


def test_repository_translates_active_scan_conflict_without_owning_rollback(
    persistence_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _store_source(persistence_session)
    repository = SqlAlchemyScanRunRepository(persistence_session)
    repository.add(_queued_run("run-1"))
    original_rollback = persistence_session.rollback
    rollback_calls = 0

    def track_rollback() -> None:
        nonlocal rollback_calls
        rollback_calls += 1
        original_rollback()

    monkeypatch.setattr(persistence_session, "rollback", track_rollback)
    conflicting = replace(_queued_run("run-2"), generation=2)

    with pytest.raises(ScanAlreadyRunningError, match="active scan or generation"):
        repository.add(conflicting)

    assert rollback_calls == 0
    original_rollback()


def test_database_enforces_unique_source_generation(
    persistence_session: Session,
) -> None:
    _store_source(persistence_session)
    _insert_run(persistence_session, "run-1", generation=1, status="completed")

    with pytest.raises(IntegrityError):
        _insert_run(persistence_session, "run-2", generation=1, status="completed")


def test_completed_history_does_not_block_new_active_generation(
    persistence_session: Session,
) -> None:
    _store_source(persistence_session)
    _insert_run(persistence_session, "completed-1", generation=1, status="completed")
    _insert_run(persistence_session, "completed-2", generation=2, status="completed")
    _insert_run(persistence_session, "queued-3", generation=3)

    persistence_session.flush()


def _store_source(session: Session) -> None:
    SqlAlchemyMediaSourceRepository(session).store(
        MediaSource(
            MediaSourceId("source-1"),
            MediaSourceKind.LOCAL,
            display_name="Source",
            configured_root="/approved/source",
            enabled=True,
        )
    )
    session.flush()


def _queued_run(identifier: str) -> ScanRun:
    return ScanRun(
        ScanRunId(identifier),
        MediaSourceId("source-1"),
        ScanKind.FULL,
        1,
        ScanStatus.QUEUED,
        False,
        _NOW,
    )


def _insert_run(
    session: Session,
    identifier: str,
    *,
    kind: str = "full",
    status: str = "queued",
    generation: int = 1,
    discovered: int = 0,
    added: int = 0,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    terminal = status == "completed"
    session.execute(
        text(
            "INSERT INTO scan_runs "
            "(id, source_id, kind, generation, status, cancellation_requested, queued_utc_us, "
            "started_utc_us, finished_utc_us, discovered_count, added_count, unchanged_count, "
            "changed_count, missing_count, ignored_count, issue_count, terminal_error_code, "
            "terminal_error_message) VALUES "
            "(:id, 'source-1', :kind, :generation, :status, 0, 1, :started, :finished, "
            ":discovered, :added, 0, 0, 0, 0, 0, :error_code, :error_message)"
        ),
        {
            "id": identifier,
            "kind": kind,
            "generation": generation,
            "status": status,
            "started": 1 if terminal else None,
            "finished": 1 if terminal else None,
            "discovered": discovered,
            "added": added,
            "error_code": error_code,
            "error_message": error_message,
        },
    )
