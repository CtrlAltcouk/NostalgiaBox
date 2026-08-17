"""Durable local scan coordination behind typed infrastructure ports."""

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol, Self

from nostalgiabox.application.sources import LocalSourceGateway, SourceRepository
from nostalgiabox.domain.catalogue import (
    FilePresenceState,
    MediaFile,
    MediaFileId,
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    SourceAvailability,
)
from nostalgiabox.domain.clock import Clock
from nostalgiabox.domain.scanning import (
    MediaFileObservation,
    ScanIssue,
    ScanIssueId,
    ScanIssueSeverity,
    ScanKind,
    ScanRun,
    ScanRunId,
    ScanStatus,
)
from nostalgiabox.domain.time import normalize_utc


class ScanApplicationError(Exception):
    """Base class for controlled scan-coordination failures."""


class ScanNotFoundError(ScanApplicationError):
    """A requested durable scan run does not exist."""


class ScanAlreadyRunningError(ScanApplicationError):
    """A source already owns a queued or running scan."""

    code = "scan.already_running"


class ScanSourceNotEligibleError(ScanApplicationError):
    """A scan was requested for a missing, disabled, retired or non-local source."""


class ScanExecutorUnavailableError(ScanApplicationError):
    """The bounded executor has no capacity for another scan."""


class TraversalFailedError(ScanApplicationError):
    """The filesystem view cannot safely authorize missing reconciliation."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True, slots=True)
class TraversalIgnored:
    """One ignored entry counted without creating an issue row."""

    category: str


@dataclass(frozen=True, slots=True)
class TraversalFileIssue:
    """A safe source-relative transient file observation problem."""

    relative_locator: str
    code: str
    message: str


type TraversalEvent = MediaFileObservation | TraversalIgnored | TraversalFileIssue


class LocalTraversalGateway(Protocol):
    """Yield deterministic local discovery events without persistence concerns."""

    def iterate(self, configured_root: str) -> Iterable[TraversalEvent]: ...


class ScanExecutor(Protocol):
    """Bound scan execution without exposing concurrency primitives to application code."""

    def submit(self, operation: Callable[[], None]) -> None: ...

    def shutdown(self, *, wait: bool = True) -> None: ...


class ScanRunRepository(Protocol):
    def add(self, run: ScanRun) -> None: ...

    def get(self, run_id: ScanRunId) -> ScanRun | None: ...

    def update(self, run: ScanRun) -> None: ...

    def next_generation(self, source_id: MediaSourceId) -> int: ...

    def has_active(self, source_id: MediaSourceId) -> bool: ...

    def list_active(self) -> tuple[ScanRun, ...]: ...


class MediaInventoryRepository(Protocol):
    def get_present(
        self, source_id: MediaSourceId, normalized_locator: str
    ) -> MediaFile | None: ...

    def list_missing(
        self, source_id: MediaSourceId, normalized_locator: str
    ) -> tuple[MediaFile, ...]: ...

    def list_unclassified(
        self, source_id: MediaSourceId, normalized_locator: str
    ) -> tuple[MediaFile, ...]: ...

    def store(self, media_file: MediaFile) -> None: ...

    def mark_unseen_missing(
        self,
        source_id: MediaSourceId,
        generation: int,
        missing_utc: datetime,
    ) -> int: ...


class ScanIssueRepository(Protocol):
    def add(self, issue: ScanIssue) -> bool: ...

    def list_for_run(self, run_id: ScanRunId) -> tuple[ScanIssue, ...]: ...


class ScanUnitOfWork(AbstractContextManager["ScanUnitOfWork"], Protocol):
    @property
    def runs(self) -> ScanRunRepository: ...

    @property
    def inventory(self) -> MediaInventoryRepository: ...

    @property
    def issues(self) -> ScanIssueRepository: ...

    @property
    def sources(self) -> SourceRepository: ...

    def __enter__(self) -> Self: ...

    def commit(self) -> None: ...


ScanUnitOfWorkFactory = Callable[[], ScanUnitOfWork]
ScanRunIdFactory = Callable[[], ScanRunId]
ScanIssueIdFactory = Callable[[], ScanIssueId]
MediaFileIdFactory = Callable[[], MediaFileId]


class _ObservationOutcome(StrEnum):
    ADDED = "added"
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    ALREADY_APPLIED = "already_applied"


class _BatchPersistenceResult(StrEnum):
    APPLIED = "applied"
    CANCELLATION_REQUESTED = "cancellation_requested"
    SOURCE_CHANGED = "source_changed"


class ScanCoordinator:
    """Create durable runs and execute local discovery in bounded short transactions."""

    def __init__(
        self,
        unit_of_work_factory: ScanUnitOfWorkFactory,
        source_gateway: LocalSourceGateway,
        traversal_gateway: LocalTraversalGateway,
        executor: ScanExecutor,
        clock: Clock,
        run_id_factory: ScanRunIdFactory,
        issue_id_factory: ScanIssueIdFactory,
        media_file_id_factory: MediaFileIdFactory,
        *,
        persistence_batch_size: int,
        progress_update_threshold: int,
    ) -> None:
        if persistence_batch_size < 1:
            raise ValueError("scan persistence batch size must be positive")
        if progress_update_threshold < 1:
            raise ValueError("scan progress threshold must be positive")
        self._unit_of_work_factory = unit_of_work_factory
        self._source_gateway = source_gateway
        self._traversal_gateway = traversal_gateway
        self._executor = executor
        self._clock = clock
        self._run_id_factory = run_id_factory
        self._issue_id_factory = issue_id_factory
        self._media_file_id_factory = media_file_id_factory
        self._event_batch_size = min(persistence_batch_size, progress_update_threshold)

    def start_scan(self, source_id: MediaSourceId, kind: ScanKind) -> ScanRun:
        """Persist one queued run and dispatch it only after the short transaction closes."""
        queued_at = self._now("scan queue")
        with self._unit_of_work_factory() as unit_of_work:
            source = _require_eligible_source(unit_of_work.sources.get_by_id(source_id))
            if unit_of_work.runs.has_active(source.id):
                raise ScanAlreadyRunningError(
                    f"source {source.id.value!r} already has an active scan"
                )
            run = ScanRun(
                id=self._run_id_factory(),
                source_id=source.id,
                kind=kind,
                generation=unit_of_work.runs.next_generation(source.id),
                status=ScanStatus.QUEUED,
                cancellation_requested=False,
                queued_utc=queued_at,
            )
            unit_of_work.runs.add(run)
            unit_of_work.commit()
        try:
            self._executor.submit(lambda: self.execute_scan(run.id))
        except ScanExecutorUnavailableError:
            self._terminate(
                run.id,
                ScanStatus.FAILED,
                "scan.executor_unavailable",
                "The bounded scan executor is currently unavailable.",
            )
            raise
        return run

    def execute_scan(self, run_id: ScanRunId) -> None:
        """Execute one queued run, retaining committed batches on every safe termination."""
        try:
            run = self._check_source_and_start(run_id)
            if run is None:
                return
            iterator = iter(self._traversal_gateway.iterate(run.source_root or ""))
            batch: list[TraversalEvent] = []
            while True:
                if self._cancellation_requested(run_id):
                    self._cancel(run_id)
                    return
                try:
                    event = next(iterator)
                except StopIteration:
                    break
                batch.append(event)
                if len(batch) >= self._event_batch_size:
                    result = self._persist_batch(run_id, tuple(batch))
                    if result is _BatchPersistenceResult.CANCELLATION_REQUESTED:
                        self._cancel(run_id)
                        return
                    if result is _BatchPersistenceResult.SOURCE_CHANGED:
                        return
                    batch.clear()
            if batch:
                result = self._persist_batch(run_id, tuple(batch))
                if result is _BatchPersistenceResult.CANCELLATION_REQUESTED:
                    self._cancel(run_id)
                    return
                if result is _BatchPersistenceResult.SOURCE_CHANGED:
                    return
            if self._cancellation_requested(run_id):
                self._cancel(run_id)
                return
            self._finalize(run_id)
        except TraversalFailedError as error:
            self._terminate(run_id, ScanStatus.FAILED, error.code, error.message)
        except Exception:
            self._terminate(
                run_id,
                ScanStatus.FAILED,
                "scan.failed",
                "The scan failed while processing a bounded discovery batch.",
            )

    def request_cancellation(self, run_id: ScanRunId) -> ScanRun:
        """Persist an idempotent cooperative cancellation request."""
        with self._unit_of_work_factory() as unit_of_work:
            run = _require_run(unit_of_work.runs, run_id)
            if run.status.is_terminal or run.cancellation_requested:
                return run
            updated = replace(run, cancellation_requested=True)
            unit_of_work.runs.update(updated)
            unit_of_work.commit()
            return updated

    def recover_abandoned_runs(self) -> tuple[ScanRun, ...]:
        """Interrupt every non-durable queued/running executor item without reconciliation."""
        recovered: list[ScanRun] = []
        finished_at = self._now("scan recovery")
        with self._unit_of_work_factory() as unit_of_work:
            for run in unit_of_work.runs.list_active():
                updated = replace(
                    run,
                    status=ScanStatus.INTERRUPTED,
                    finished_utc=finished_at,
                    terminal_error_code="scan.interrupted",
                    terminal_error_message="The scan was interrupted by application restart.",
                )
                unit_of_work.runs.update(updated)
                issue_added = unit_of_work.issues.add(
                    self._issue(
                        run.id,
                        "terminal:scan.interrupted",
                        "scan.interrupted",
                        "The scan was interrupted by application restart.",
                        ScanIssueSeverity.WARNING,
                        finished_at,
                    )
                )
                if issue_added:
                    updated = replace(updated, counters=updated.counters.plus(issues=1))
                    unit_of_work.runs.update(updated)
                recovered.append(updated)
            if recovered:
                unit_of_work.commit()
        return tuple(recovered)

    def _check_source_and_start(self, run_id: ScanRunId) -> ScanRun | None:
        with self._unit_of_work_factory() as unit_of_work:
            run = _require_run(unit_of_work.runs, run_id)
            if run.status is not ScanStatus.QUEUED:
                return None
            source = _require_eligible_source(unit_of_work.sources.get_by_id(run.source_id))
        if run.cancellation_requested:
            self._cancel(run.id)
            return None
        assert source.configured_root is not None
        availability = self._source_gateway.check(source.configured_root)
        checked_at = self._now("scan source availability")

        with self._unit_of_work_factory() as unit_of_work:
            current_run = _require_run(unit_of_work.runs, run.id)
            current_source = _require_eligible_source(unit_of_work.sources.get_by_id(source.id))
            if current_source.revision != source.revision or (
                current_source.configured_root != source.configured_root
            ):
                self._interrupt_in_uow(
                    unit_of_work,
                    current_run,
                    "scan.source_changed",
                    "The source configuration changed before scanning began.",
                    checked_at,
                )
                unit_of_work.commit()
                return None
            updated_source = replace(
                current_source,
                availability=availability.availability,
                last_checked_utc=checked_at,
                current_error_code=availability.error_code,
                current_error_message=availability.error_message,
                revision=current_source.revision + 1,
            )
            if not unit_of_work.sources.update(updated_source, current_source.revision):
                raise ScanApplicationError("source changed during scan availability update")
            if availability.availability is not SourceAvailability.AVAILABLE:
                failed = replace(
                    current_run,
                    status=ScanStatus.FAILED,
                    finished_utc=checked_at,
                    source_revision=updated_source.revision,
                    source_root=updated_source.configured_root,
                    terminal_error_code="scan.source_unavailable",
                    terminal_error_message="The configured source is not available for scanning.",
                )
                failed = self._add_issue_in_uow(
                    unit_of_work,
                    failed,
                    "terminal:scan.source_unavailable",
                    "scan.source_unavailable",
                    "The configured source is not available for scanning.",
                    ScanIssueSeverity.ERROR,
                    checked_at,
                )
                unit_of_work.runs.update(failed)
                unit_of_work.commit()
                return None
            running = replace(
                current_run,
                status=ScanStatus.RUNNING,
                started_utc=checked_at,
                source_revision=updated_source.revision,
                source_root=updated_source.configured_root,
            )
            unit_of_work.runs.update(running)
            unit_of_work.commit()
            return running

    def _persist_batch(
        self, run_id: ScanRunId, events: tuple[TraversalEvent, ...]
    ) -> _BatchPersistenceResult:
        observed_at = self._now("scan observation")
        with self._unit_of_work_factory() as unit_of_work:
            run = _require_run(unit_of_work.runs, run_id)
            if run.status is not ScanStatus.RUNNING or run.cancellation_requested:
                return _BatchPersistenceResult.CANCELLATION_REQUESTED
            source = unit_of_work.sources.get_by_id(run.source_id)
            if not _source_matches_snapshot(source, run):
                self._interrupt_in_uow(
                    unit_of_work,
                    run,
                    "scan.source_changed",
                    "The source changed before a discovery batch could be persisted.",
                    observed_at,
                )
                unit_of_work.commit()
                return _BatchPersistenceResult.SOURCE_CHANGED
            counters = run.counters
            for event in events:
                if isinstance(event, TraversalIgnored):
                    counters = counters.plus(ignored=1)
                    continue
                if isinstance(event, TraversalFileIssue):
                    issue_added = unit_of_work.issues.add(
                        self._issue(
                            run.id,
                            f"{event.code}:{event.relative_locator}",
                            event.code,
                            event.message,
                            ScanIssueSeverity.WARNING,
                            observed_at,
                            relative_locator=event.relative_locator,
                        )
                    )
                    if issue_added:
                        counters = counters.plus(issues=1)
                    continue
                outcome, media_file, ambiguous = self._apply_observation(
                    unit_of_work.inventory,
                    run,
                    event,
                    observed_at,
                )
                if outcome is _ObservationOutcome.ALREADY_APPLIED:
                    continue
                if outcome is _ObservationOutcome.ADDED:
                    counters = counters.plus(discovered=1, added=1)
                elif outcome is _ObservationOutcome.CHANGED:
                    counters = counters.plus(discovered=1, changed=1)
                else:
                    counters = counters.plus(discovered=1, unchanged=1)
                if outcome is _ObservationOutcome.CHANGED and unit_of_work.issues.add(
                    self._issue(
                        run.id,
                        f"file.changed_observation:{event.normalized_relative_locator}",
                        "file.changed_observation",
                        "The cheap observation changed; identity remains provisional.",
                        ScanIssueSeverity.WARNING,
                        observed_at,
                        media_file_id=media_file.id,
                        relative_locator=event.normalized_relative_locator,
                    )
                ):
                    counters = counters.plus(issues=1)
                if ambiguous and unit_of_work.issues.add(
                    self._issue(
                        run.id,
                        f"scan.ambiguous_legacy_locator:{event.normalized_relative_locator}",
                        "scan.ambiguous_legacy_locator",
                        "Several historical files share this locator; none was merged.",
                        ScanIssueSeverity.WARNING,
                        observed_at,
                        media_file_id=media_file.id,
                        relative_locator=event.normalized_relative_locator,
                    )
                ):
                    counters = counters.plus(issues=1)
            unit_of_work.runs.update(replace(run, counters=counters))
            unit_of_work.commit()
            return _BatchPersistenceResult.APPLIED

    def _apply_observation(
        self,
        inventory: MediaInventoryRepository,
        run: ScanRun,
        observation: MediaFileObservation,
        observed_at: datetime,
    ) -> tuple[_ObservationOutcome, MediaFile, bool]:
        present = inventory.get_present(run.source_id, observation.normalized_relative_locator)
        if present is not None and present.last_seen_generation == run.generation:
            return _ObservationOutcome.ALREADY_APPLIED, present, False
        ambiguous = False
        candidate = present
        added = False
        if candidate is None:
            missing = inventory.list_missing(run.source_id, observation.normalized_relative_locator)
            if len(missing) == 1:
                candidate = missing[0]
            elif len(missing) > 1:
                ambiguous = True
            else:
                historical = inventory.list_unclassified(
                    run.source_id, observation.normalized_relative_locator
                )
                if len(historical) == 1:
                    candidate = historical[0]
                    added = True
                elif len(historical) > 1:
                    ambiguous = True
            if candidate is None:
                candidate = MediaFile(
                    id=self._media_file_id_factory(),
                    source_id=run.source_id,
                    normalized_relative_locator=observation.normalized_relative_locator,
                    original_relative_locator=observation.original_relative_locator,
                )
                added = True
        old_signature = (
            candidate.normalized_relative_locator,
            candidate.size_bytes,
            candidate.modified_time_ns,
        )
        changed = (
            candidate.presence is not FilePresenceState.UNCLASSIFIED
            and old_signature != observation.cheap_signature
        )
        first_observed = candidate.first_observed_utc or observed_at
        updated = replace(
            candidate,
            normalized_relative_locator=observation.normalized_relative_locator,
            original_relative_locator=observation.original_relative_locator,
            presence=FilePresenceState.PRESENT,
            size_bytes=observation.size_bytes,
            modified_time_ns=observation.modified_time_ns,
            device_id=observation.device_id,
            inode_id=observation.inode_id,
            last_seen_generation=run.generation,
            first_observed_utc=first_observed,
            last_observed_utc=observed_at,
            missing_since_utc=None,
        )
        inventory.store(updated)
        if added:
            return _ObservationOutcome.ADDED, updated, ambiguous
        if changed:
            return _ObservationOutcome.CHANGED, updated, ambiguous
        return _ObservationOutcome.UNCHANGED, updated, ambiguous

    def _finalize(self, run_id: ScanRunId) -> None:
        finished_at = self._now("scan completion")
        with self._unit_of_work_factory() as unit_of_work:
            run = _require_run(unit_of_work.runs, run_id)
            if run.status is not ScanStatus.RUNNING:
                return
            if run.cancellation_requested:
                self._cancel_in_uow(unit_of_work, run, finished_at)
                unit_of_work.commit()
                return
            source = unit_of_work.sources.get_by_id(run.source_id)
            if not _source_matches_snapshot(source, run):
                self._interrupt_in_uow(
                    unit_of_work,
                    run,
                    "scan.source_changed",
                    "The source changed before scan reconciliation.",
                    finished_at,
                )
                unit_of_work.commit()
                return
            assert source is not None
            missing_count = unit_of_work.inventory.mark_unseen_missing(
                run.source_id, run.generation, finished_at
            )
            updated_source = replace(
                source,
                last_successful_scan_utc=finished_at,
                revision=source.revision + 1,
            )
            if not unit_of_work.sources.update(updated_source, source.revision):
                raise ScanApplicationError("source changed during scan reconciliation")
            completed = replace(
                run,
                status=ScanStatus.COMPLETED,
                finished_utc=finished_at,
                counters=run.counters.plus(missing=missing_count),
            )
            unit_of_work.runs.update(completed)
            unit_of_work.commit()

    def _cancellation_requested(self, run_id: ScanRunId) -> bool:
        with self._unit_of_work_factory() as unit_of_work:
            return _require_run(unit_of_work.runs, run_id).cancellation_requested

    def _cancel(self, run_id: ScanRunId) -> None:
        cancelled_at = self._now("scan cancellation")
        with self._unit_of_work_factory() as unit_of_work:
            run = _require_run(unit_of_work.runs, run_id)
            if run.status.is_terminal:
                return
            self._cancel_in_uow(unit_of_work, run, cancelled_at)
            unit_of_work.commit()

    def _cancel_in_uow(
        self, unit_of_work: ScanUnitOfWork, run: ScanRun, cancelled_at: datetime
    ) -> None:
        cancelled = replace(
            run,
            status=ScanStatus.CANCELLED,
            cancellation_requested=True,
            finished_utc=cancelled_at,
            terminal_error_code="scan.cancelled",
            terminal_error_message="The scan was cancelled.",
        )
        cancelled = self._add_issue_in_uow(
            unit_of_work,
            cancelled,
            "terminal:scan.cancelled",
            "scan.cancelled",
            "The scan was cancelled.",
            ScanIssueSeverity.INFO,
            cancelled_at,
        )
        unit_of_work.runs.update(cancelled)

    def _terminate(
        self,
        run_id: ScanRunId,
        status: ScanStatus,
        code: str,
        message: str,
    ) -> None:
        finished_at = self._now("scan termination")
        try:
            with self._unit_of_work_factory() as unit_of_work:
                run = _require_run(unit_of_work.runs, run_id)
                if run.status.is_terminal:
                    return
                terminated = replace(
                    run,
                    status=status,
                    finished_utc=finished_at,
                    terminal_error_code=code,
                    terminal_error_message=message,
                )
                terminated = self._add_issue_in_uow(
                    unit_of_work,
                    terminated,
                    f"terminal:{code}",
                    code,
                    message,
                    ScanIssueSeverity.ERROR,
                    finished_at,
                )
                unit_of_work.runs.update(terminated)
                unit_of_work.commit()
        except Exception:
            return

    def _interrupt_in_uow(
        self,
        unit_of_work: ScanUnitOfWork,
        run: ScanRun,
        code: str,
        message: str,
        finished_at: datetime,
    ) -> None:
        interrupted = replace(
            run,
            status=ScanStatus.INTERRUPTED,
            finished_utc=finished_at,
            terminal_error_code=code,
            terminal_error_message=message,
        )
        interrupted = self._add_issue_in_uow(
            unit_of_work,
            interrupted,
            f"terminal:{code}",
            code,
            message,
            ScanIssueSeverity.WARNING,
            finished_at,
        )
        unit_of_work.runs.update(interrupted)

    def _add_issue_in_uow(
        self,
        unit_of_work: ScanUnitOfWork,
        run: ScanRun,
        deduplication_key: str,
        code: str,
        message: str,
        severity: ScanIssueSeverity,
        occurred_at: datetime,
    ) -> ScanRun:
        if unit_of_work.issues.add(
            self._issue(
                run.id,
                deduplication_key,
                code,
                message,
                severity,
                occurred_at,
            )
        ):
            return replace(run, counters=run.counters.plus(issues=1))
        return run

    def _issue(
        self,
        run_id: ScanRunId,
        deduplication_key: str,
        code: str,
        message: str,
        severity: ScanIssueSeverity,
        occurred_at: datetime,
        *,
        media_file_id: MediaFileId | None = None,
        relative_locator: str | None = None,
    ) -> ScanIssue:
        return ScanIssue(
            id=self._issue_id_factory(),
            run_id=run_id,
            deduplication_key=deduplication_key,
            code=code,
            message=message,
            occurred_utc=occurred_at,
            severity=severity,
            media_file_id=media_file_id,
            relative_locator=relative_locator,
        )

    def _now(self, field_name: str) -> datetime:
        return normalize_utc(self._clock.now(), field_name=field_name)


def _require_run(repository: ScanRunRepository, run_id: ScanRunId) -> ScanRun:
    run = repository.get(run_id)
    if run is None:
        raise ScanNotFoundError(f"scan {run_id.value!r} was not found")
    return run


def _require_eligible_source(source: MediaSource | None) -> MediaSource:
    if source is None:
        raise ScanSourceNotEligibleError("scan source was not found")
    if source.kind is not MediaSourceKind.LOCAL:
        raise ScanSourceNotEligibleError("scan source is not local")
    if not source.enabled:
        raise ScanSourceNotEligibleError("scan source is disabled")
    if source.retired_utc is not None:
        raise ScanSourceNotEligibleError("scan source is retired")
    if source.configured_root is None:
        raise ScanSourceNotEligibleError("scan source has no configured root")
    return source


def _source_matches_snapshot(source: MediaSource | None, run: ScanRun) -> bool:
    return bool(
        source is not None
        and source.id == run.source_id
        and source.kind is MediaSourceKind.LOCAL
        and source.enabled
        and source.retired_utc is None
        and source.configured_root == run.source_root
        and source.revision == run.source_revision
    )
