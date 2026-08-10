"""Durable local scan coordination against disposable SQLite persistence."""

from collections.abc import Callable, Iterable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from nostalgiabox.application.scans import (
    LocalTraversalGateway,
    ScanAlreadyRunningError,
    ScanCoordinator,
    ScanExecutor,
    ScanSourceNotEligibleError,
    TraversalEvent,
    TraversalFailedError,
)
from nostalgiabox.application.sources import LocalSourceGateway, SourceAvailabilityResult
from nostalgiabox.domain import (
    ChannelId,
    FilePresenceState,
    MediaFile,
    MediaFileId,
    MediaFileObservation,
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    ScanIssueId,
    ScanKind,
    ScanRun,
    ScanRunId,
    ScanStatus,
    SourceAvailability,
)
from nostalgiabox.persistence.catalogue_mappers import media_file_from_record
from nostalgiabox.persistence.catalogue_repositories import SqlAlchemyMediaSourceRepository
from nostalgiabox.persistence.models import (
    CatalogueItemRecord,
    MediaFileRecord,
    MediaItemRecord,
    PlayableRenditionRecord,
    ScanRunRecord,
)
from nostalgiabox.persistence.runtime_sources import SqlAlchemyRuntimeDataSource
from nostalgiabox.persistence.scan_repositories import (
    SqlAlchemyMediaInventoryRepository,
    SqlAlchemyScanIssueRepository,
    SqlAlchemyScanRunRepository,
)
from nostalgiabox.persistence.scan_uow import SqlAlchemyScanUnitOfWork
from nostalgiabox.source.local import LocalFilesystemSourceGateway
from nostalgiabox.source.traversal import LocalFilesystemTraversalGateway
from tests.support.clock import FakeClock

_START = datetime(2026, 8, 10, 12, tzinfo=UTC)


def test_real_temporary_local_scan_discovers_only_physical_eligible_files(
    persistence_engine: Engine,
    tmp_path: Path,
) -> None:
    root = tmp_path / "media"
    nested = root / "nested"
    hidden = root / ".hidden"
    nested.mkdir(parents=True)
    hidden.mkdir()
    eligible = nested / "episode.MKV"
    eligible.write_bytes(b"episode")
    (root / "notes.txt").write_text("ignored", encoding="utf-8")
    (hidden / "secret.mkv").write_bytes(b"hidden")
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory, configured_root=str(root))
    source_gateway = LocalFilesystemSourceGateway([str(root)])
    traversal = LocalFilesystemTraversalGateway(source_gateway, (".mkv",))
    coordinator = _coordinator(
        factory,
        traversal,
        source_gateway,
        _InlineExecutor(),
        FakeClock(_START),
    )

    run = _completed(coordinator, factory, source.id, ScanKind.FULL)
    files = _files(factory, source.id)

    assert run.counters.added == run.counters.discovered == 1
    assert run.counters.ignored == 2
    assert len(files) == 1
    assert files[0].normalized_relative_locator == "nested/episode.MKV"
    assert files[0].size_bytes == len(b"episode")
    assert files[0].modified_time_ns == eligible.stat().st_mtime_ns
    assert _logical_counts(factory) == (0, 0, 0)


@pytest.mark.parametrize("case", ["missing", "smb", "disabled", "retired", "rootless"])
def test_scan_rejects_ineligible_source_before_creating_run(
    persistence_engine: Engine,
    case: str,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source_id = MediaSourceId("source-1")
    if case != "missing":
        source = MediaSource(
            source_id,
            MediaSourceKind.SMB if case == "smb" else MediaSourceKind.LOCAL,
            display_name="Source",
            configured_root=None if case == "rootless" else "/approved/source",
            enabled=case not in {"disabled", "retired"},
            retired_utc=_START if case == "retired" else None,
        )
        with factory() as session:
            SqlAlchemyMediaSourceRepository(session).store(source)
            session.commit()
    coordinator = _coordinator(
        factory,
        _MutableTraversal([]),
        _AvailableGateway(),
        _DeferredExecutor(),
        FakeClock(_START),
    )

    with pytest.raises(ScanSourceNotEligibleError):
        coordinator.start_scan(source_id, ScanKind.FULL)

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ScanRunRecord)) == 0


def test_initial_unchanged_add_change_remove_and_reappear_lifecycle(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory)
    clock = FakeClock(_START)
    traversal = _MutableTraversal([_observation("one.mkv", 3, 10)])
    coordinator = _coordinator(factory, traversal, _AvailableGateway(), _InlineExecutor(), clock)

    first = _completed(coordinator, factory, source.id, ScanKind.FULL)
    files = _files(factory, source.id)
    assert first.counters.discovered == first.counters.added == 1
    assert first.counters.unchanged == first.counters.changed == first.counters.missing == 0
    assert len(files) == 1
    original_id = files[0].id
    assert files[0].presence is FilePresenceState.PRESENT
    assert files[0].size_bytes == 3
    assert files[0].modified_time_ns == 10
    assert files[0].last_seen_generation == 1
    assert _logical_counts(factory) == (0, 0, 0)
    first_success = _source(factory, source.id).last_successful_scan_utc
    assert first_success == _START

    clock.advance(timedelta(minutes=1))
    second = _completed(coordinator, factory, source.id, ScanKind.INCREMENTAL)
    assert second.generation == 2
    assert second.counters.unchanged == 1
    assert (
        next(
            item.id
            for item in _files(factory, source.id)
            if item.normalized_relative_locator == "one.mkv"
        )
        == original_id
    )
    assert _source(factory, source.id).last_successful_scan_utc == clock.current

    clock.advance(timedelta(minutes=1))
    traversal.events.append(_observation("two.MP4", 4, 20))
    third = _completed(coordinator, factory, source.id, ScanKind.INCREMENTAL)
    assert (third.counters.unchanged, third.counters.added) == (1, 1)
    files = _files(factory, source.id)
    assert len(files) == 2
    second_id = next(item.id for item in files if item.id != original_id)

    clock.advance(timedelta(minutes=1))
    traversal.events[0] = _observation("one.mkv", 8, 30)
    fourth = _completed(coordinator, factory, source.id, ScanKind.FULL)
    assert (fourth.counters.changed, fourth.counters.unchanged) == (1, 1)
    assert (
        next(
            item.id
            for item in _files(factory, source.id)
            if item.normalized_relative_locator == "one.mkv"
        )
        == original_id
    )
    assert "file.changed_observation" in _issue_codes(factory, fourth.id)

    clock.advance(timedelta(minutes=1))
    traversal.events = [traversal.events[0]]
    fifth = _completed(coordinator, factory, source.id, ScanKind.FULL)
    assert fifth.counters.missing == 1
    missing = next(item for item in _files(factory, source.id) if item.id == second_id)
    assert missing.presence is FilePresenceState.MISSING
    assert missing.missing_since_utc == clock.current

    clock.advance(timedelta(minutes=1))
    traversal.events.append(_observation("two.MP4", 4, 20))
    sixth = _completed(coordinator, factory, source.id, ScanKind.FULL)
    reappeared = next(item for item in _files(factory, source.id) if item.id == second_id)
    assert reappeared.presence is FilePresenceState.PRESENT
    assert reappeared.missing_since_utc is None
    assert sixth.counters.unchanged == 2


def test_unavailable_source_fails_without_traversal_or_missing_reconciliation(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory)
    clock = FakeClock(_START)
    traversal = _MutableTraversal([_observation("one.mkv", 3, 10)])
    gateway = _AvailableGateway()
    coordinator = _coordinator(factory, traversal, gateway, _InlineExecutor(), clock)
    _completed(coordinator, factory, source.id, ScanKind.FULL)
    successful_at = _source(factory, source.id).last_successful_scan_utc
    gateway.result = SourceAvailabilityResult(
        SourceAvailability.UNAVAILABLE,
        "source.unavailable",
        "The source is unavailable.",
    )
    traversal.calls = 0

    queued = coordinator.start_scan(source.id, ScanKind.FULL)
    failed = _run(factory, queued.id)

    assert failed.status is ScanStatus.FAILED
    assert failed.terminal_error_code == "scan.source_unavailable"
    assert traversal.calls == 0
    assert _files(factory, source.id)[0].presence is FilePresenceState.PRESENT
    assert _source(factory, source.id).last_successful_scan_utc == successful_at


def test_traversal_failure_keeps_committed_batch_and_never_marks_unseen_missing(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory)
    clock = FakeClock(_START)
    traversal = _MutableTraversal([_observation("one.mkv", 3, 10), _observation("two.mkv", 4, 20)])
    coordinator = _coordinator(factory, traversal, _AvailableGateway(), _InlineExecutor(), clock)
    _completed(coordinator, factory, source.id, ScanKind.FULL)
    successful_at = _source(factory, source.id).last_successful_scan_utc
    clock.advance(timedelta(minutes=1))
    traversal.failure_after = 1

    queued = coordinator.start_scan(source.id, ScanKind.FULL)
    failed = _run(factory, queued.id)

    assert failed.status is ScanStatus.FAILED
    assert failed.terminal_error_code == "scan.traversal_failed"
    assert all(item.presence is FilePresenceState.PRESENT for item in _files(factory, source.id))
    assert _source(factory, source.id).last_successful_scan_utc == successful_at


def test_cancellation_after_committed_batch_preserves_batch_and_skips_reconciliation(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory)
    executor = _DeferredExecutor()
    clock = FakeClock(_START)
    traversal = _CallbackTraversal(_observation("one.mkv", 1, 1), _observation("two.mkv", 2, 2))
    coordinator = _coordinator(
        factory,
        traversal,
        _AvailableGateway(),
        executor,
        clock,
        batch_size=1,
    )
    queued = coordinator.start_scan(source.id, ScanKind.FULL)
    traversal.callback = lambda: coordinator.request_cancellation(queued.id)

    executor.run_next()
    cancelled = _run(factory, queued.id)

    assert cancelled.status is ScanStatus.CANCELLED
    assert cancelled.cancellation_requested
    assert [item.normalized_relative_locator for item in _files(factory, source.id)] == ["one.mkv"]
    assert _source(factory, source.id).last_successful_scan_utc is None
    assert coordinator.request_cancellation(queued.id) == cancelled


def test_source_change_during_scan_interrupts_without_missing_reconciliation(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory)
    clock = FakeClock(_START)
    seed = _MutableTraversal([_observation("one.mkv", 1, 1), _observation("two.mkv", 2, 2)])
    coordinator = _coordinator(factory, seed, _AvailableGateway(), _InlineExecutor(), clock)
    _completed(coordinator, factory, source.id, ScanKind.FULL)
    successful_at = _source(factory, source.id).last_successful_scan_utc
    deferred = _DeferredExecutor()
    traversal = _CallbackTraversal(_observation("one.mkv", 1, 1))
    coordinator = _coordinator(factory, traversal, _AvailableGateway(), deferred, clock)
    queued = coordinator.start_scan(source.id, ScanKind.FULL)

    def disable_source() -> None:
        with factory() as session:
            repository = SqlAlchemyMediaSourceRepository(session)
            current = repository.get_by_id(source.id)
            assert current is not None
            repository.update(
                replace(current, enabled=False, revision=current.revision + 1), current.revision
            )
            session.commit()

    traversal.callback = disable_source
    deferred.run_next()
    interrupted = _run(factory, queued.id)

    assert interrupted.status is ScanStatus.INTERRUPTED
    assert interrupted.terminal_error_code == "scan.source_changed"
    assert all(item.presence is FilePresenceState.PRESENT for item in _files(factory, source.id))
    assert _source(factory, source.id).last_successful_scan_utc == successful_at


def test_one_active_scan_application_guard_recovery_and_new_generation(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    first_source = _store_source(factory, "source-1")
    second_source = _store_source(factory, "source-2")
    executor = _DeferredExecutor()
    coordinator = _coordinator(
        factory,
        _MutableTraversal([]),
        _AvailableGateway(),
        executor,
        FakeClock(_START),
    )
    first = coordinator.start_scan(first_source.id, ScanKind.FULL)
    with pytest.raises(ScanAlreadyRunningError, match="active scan"):
        coordinator.start_scan(first_source.id, ScanKind.INCREMENTAL)
    second = coordinator.start_scan(second_source.id, ScanKind.FULL)
    with factory() as session:
        repository = SqlAlchemyScanRunRepository(session)
        current = repository.get(second.id)
        assert current is not None
        running = replace(
            current,
            status=ScanStatus.RUNNING,
            started_utc=_START,
            source_revision=1,
            source_root="/approved/source-2",
        )
        repository.update(running)
        session.commit()

    recovered = coordinator.recover_abandoned_runs()

    assert {run.id for run in recovered} == {first.id, second.id}
    assert all(run.status is ScanStatus.INTERRUPTED for run in recovered)
    assert coordinator.recover_abandoned_runs() == ()
    replacement = coordinator.start_scan(first_source.id, ScanKind.FULL)
    assert replacement.generation == 2


def test_ambiguous_legacy_locator_creates_new_present_identity_and_safe_issue(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory)
    with factory() as session:
        inventory = SqlAlchemyMediaInventoryRepository(session)
        for identifier in ("legacy-1", "legacy-2"):
            inventory.store(MediaFile(MediaFileId(identifier), source.id, "same.mkv", "same.mkv"))
        session.commit()
    coordinator = _coordinator(
        factory,
        _MutableTraversal([_observation("same.mkv", 1, 1)]),
        _AvailableGateway(),
        _InlineExecutor(),
        FakeClock(_START),
    )

    run = _completed(coordinator, factory, source.id, ScanKind.FULL)
    files = _files(factory, source.id)

    assert len(files) == 3
    assert sum(item.presence is FilePresenceState.UNCLASSIFIED for item in files) == 2
    assert sum(item.presence is FilePresenceState.PRESENT for item in files) == 1
    assert "scan.ambiguous_legacy_locator" in _issue_codes(factory, run.id)


def test_single_legacy_locator_is_adopted_without_changing_identity(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory)
    legacy = MediaFile(MediaFileId("legacy-1"), source.id, "same.mkv", "same.mkv")
    with factory() as session:
        SqlAlchemyMediaInventoryRepository(session).store(legacy)
        session.commit()
    coordinator = _coordinator(
        factory,
        _MutableTraversal([_observation("same.mkv", 1, 1)]),
        _AvailableGateway(),
        _InlineExecutor(),
        FakeClock(_START),
    )

    run = _completed(coordinator, factory, source.id, ScanKind.FULL)

    assert _files(factory, source.id)[0].id == legacy.id
    assert _files(factory, source.id)[0].presence is FilePresenceState.PRESENT
    assert run.counters.added == 1
    assert "scan.ambiguous_legacy_locator" not in _issue_codes(factory, run.id)


def test_replayed_observation_batch_is_idempotent(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory)
    observation = _observation("same.mkv", 1, 1)
    coordinator = _coordinator(
        factory,
        _MutableTraversal([observation, observation]),
        _AvailableGateway(),
        _InlineExecutor(),
        FakeClock(_START),
        batch_size=1,
    )

    run = _completed(coordinator, factory, source.id, ScanKind.FULL)

    assert len(_files(factory, source.id)) == 1
    assert run.counters.discovered == run.counters.added == 1


def test_phase2_runtime_reads_same_database_during_scan_without_scanner_writes(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, autoflush=False, expire_on_commit=False)
    source = _store_source(factory)
    with factory() as session:
        session.execute(
            text(
                "INSERT INTO media_items VALUES "
                "('media-1', 'Programme', 60000000, '/phase2/programme.mkv')"
            )
        )
        session.execute(text("INSERT INTO channels VALUES ('channel-1', 1, 'Channel 001')"))
        session.execute(
            text(
                "INSERT INTO timeline_entries VALUES "
                "('entry-1', 'channel-1', 'media-1', 'programme', 0, 60000000)"
            )
        )
        session.commit()
    runtime = SqlAlchemyRuntimeDataSource(factory)
    traversal = _CallbackTraversal(_observation("physical.mkv", 1, 1))
    reads: list[str] = []

    def read_runtime() -> None:
        timeline = runtime.load(ChannelId("channel-1"))
        for _ in range(3):
            reads.append(runtime.get_path(timeline.entries[0].media_item_id))

    traversal.callback = read_runtime
    coordinator = _coordinator(
        factory,
        traversal,
        _AvailableGateway(),
        _InlineExecutor(),
        FakeClock(_START),
    )

    _completed(coordinator, factory, source.id, ScanKind.FULL)

    assert reads == ["/phase2/programme.mkv"] * 3
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(MediaItemRecord)) == 1
        assert session.scalar(text("SELECT COUNT(*) FROM channels")) == 1
        assert session.scalar(text("SELECT COUNT(*) FROM timeline_entries")) == 1


class _AvailableGateway:
    def __init__(self) -> None:
        self.result = SourceAvailabilityResult(SourceAvailability.AVAILABLE)

    def validate_root(self, configured_root: str) -> str:
        return configured_root

    def check(self, configured_root: str) -> SourceAvailabilityResult:
        return self.result


class _MutableTraversal:
    def __init__(self, events: list[TraversalEvent]) -> None:
        self.events = events
        self.failure_after: int | None = None
        self.calls = 0

    def iterate(self, configured_root: str) -> Iterable[TraversalEvent]:
        self.calls += 1
        for index, event in enumerate(tuple(self.events)):
            if self.failure_after is not None and index >= self.failure_after:
                raise TraversalFailedError(
                    "scan.traversal_failed", "The source could not be completely enumerated."
                )
            yield event


class _CallbackTraversal:
    def __init__(self, *events: TraversalEvent) -> None:
        self.events = events
        self.callback: Callable[[], object] = lambda: None

    def iterate(self, configured_root: str) -> Iterable[TraversalEvent]:
        for index, event in enumerate(self.events):
            if index == 1 or (index == 0 and len(self.events) == 1):
                self.callback()
            yield event
        if not self.events:
            self.callback()


class _InlineExecutor:
    def submit(self, operation: Callable[[], None]) -> None:
        operation()

    def shutdown(self, *, wait: bool = True) -> None:
        return None


class _DeferredExecutor:
    def __init__(self) -> None:
        self.operations: list[Callable[[], None]] = []

    def submit(self, operation: Callable[[], None]) -> None:
        self.operations.append(operation)

    def shutdown(self, *, wait: bool = True) -> None:
        return None

    def run_next(self) -> None:
        self.operations.pop(0)()


def _coordinator(
    factory: sessionmaker[Session],
    traversal: LocalTraversalGateway,
    source_gateway: LocalSourceGateway,
    executor: ScanExecutor,
    clock: FakeClock,
    *,
    batch_size: int = 2,
) -> ScanCoordinator:
    return ScanCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory),
        source_gateway,
        traversal,
        executor,
        clock,
        lambda: ScanRunId(f"run-{uuid4()}"),
        lambda: ScanIssueId(f"issue-{uuid4()}"),
        lambda: MediaFileId(f"file-{uuid4()}"),
        persistence_batch_size=batch_size,
        progress_update_threshold=batch_size,
    )


def _store_source(
    factory: sessionmaker[Session],
    identifier: str = "source-1",
    *,
    configured_root: str | None = None,
) -> MediaSource:
    source = MediaSource(
        MediaSourceId(identifier),
        MediaSourceKind.LOCAL,
        display_name=identifier,
        configured_root=configured_root or f"/approved/{identifier}",
        enabled=True,
    )
    with factory() as session:
        SqlAlchemyMediaSourceRepository(session).store(source)
        session.commit()
    return source


def _completed(
    coordinator: ScanCoordinator,
    factory: sessionmaker[Session],
    source_id: MediaSourceId,
    kind: ScanKind,
) -> ScanRun:
    queued = coordinator.start_scan(source_id, kind)
    run = _run(factory, queued.id)
    assert run.status is ScanStatus.COMPLETED
    return run


def _run(factory: sessionmaker[Session], run_id: ScanRunId) -> ScanRun:
    with factory() as session:
        run = SqlAlchemyScanRunRepository(session).get(run_id)
        assert run is not None
        return run


def _source(factory: sessionmaker[Session], source_id: MediaSourceId) -> MediaSource:
    with factory() as session:
        source = SqlAlchemyMediaSourceRepository(session).get_by_id(source_id)
        assert source is not None
        return source


def _files(factory: sessionmaker[Session], source_id: MediaSourceId) -> tuple[MediaFile, ...]:
    with factory() as session:
        records = session.scalars(
            select(MediaFileRecord)
            .where(MediaFileRecord.source_id == source_id.value)
            .order_by(MediaFileRecord.id)
        ).all()
        return tuple(media_file_from_record(record) for record in records)


def _issue_codes(factory: sessionmaker[Session], run_id: ScanRunId) -> set[str]:
    with factory() as session:
        return {issue.code for issue in SqlAlchemyScanIssueRepository(session).list_for_run(run_id)}


def _logical_counts(factory: sessionmaker[Session]) -> tuple[int, int, int]:
    with factory() as session:
        catalogue = session.scalar(select(func.count()).select_from(CatalogueItemRecord)) or 0
        renditions = session.scalar(select(func.count()).select_from(PlayableRenditionRecord)) or 0
        media = session.scalar(select(func.count()).select_from(MediaItemRecord)) or 0
        return catalogue, renditions, media


def _observation(locator: str, size: int, modified: int) -> MediaFileObservation:
    return MediaFileObservation(locator, locator, size, modified, 1, size + 100)
