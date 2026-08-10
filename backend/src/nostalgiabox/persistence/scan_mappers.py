"""Conversion boundary for durable scan runs and sanitized issues."""

from datetime import datetime

from nostalgiabox.domain.catalogue import MediaFileId, MediaSourceId
from nostalgiabox.domain.scanning import (
    ScanCounters,
    ScanDomainError,
    ScanIssue,
    ScanIssueId,
    ScanIssueSeverity,
    ScanKind,
    ScanRun,
    ScanRunId,
    ScanStatus,
)
from nostalgiabox.persistence.codecs import (
    datetime_to_epoch_microseconds,
    epoch_microseconds_to_datetime,
)
from nostalgiabox.persistence.errors import PersistenceConversionError
from nostalgiabox.persistence.models import ScanIssueRecord, ScanRunRecord


def scan_run_to_record(run: ScanRun) -> ScanRunRecord:
    return ScanRunRecord(
        id=run.id.value,
        source_id=run.source_id.value,
        kind=run.kind.value,
        generation=run.generation,
        status=run.status.value,
        cancellation_requested=run.cancellation_requested,
        queued_utc_us=datetime_to_epoch_microseconds(run.queued_utc),
        started_utc_us=_optional_encode(run.started_utc),
        finished_utc_us=_optional_encode(run.finished_utc),
        source_revision=run.source_revision,
        source_root=run.source_root,
        discovered_count=run.counters.discovered,
        added_count=run.counters.added,
        unchanged_count=run.counters.unchanged,
        changed_count=run.counters.changed,
        missing_count=run.counters.missing,
        ignored_count=run.counters.ignored,
        issue_count=run.counters.issues,
        terminal_error_code=run.terminal_error_code,
        terminal_error_message=run.terminal_error_message,
    )


def scan_run_from_record(record: ScanRunRecord) -> ScanRun:
    try:
        return ScanRun(
            id=ScanRunId(record.id),
            source_id=MediaSourceId(record.source_id),
            kind=ScanKind(record.kind),
            generation=record.generation,
            status=ScanStatus(record.status),
            cancellation_requested=record.cancellation_requested,
            queued_utc=epoch_microseconds_to_datetime(record.queued_utc_us),
            started_utc=_optional_decode(record.started_utc_us),
            finished_utc=_optional_decode(record.finished_utc_us),
            source_revision=record.source_revision,
            source_root=record.source_root,
            counters=ScanCounters(
                discovered=record.discovered_count,
                added=record.added_count,
                unchanged=record.unchanged_count,
                changed=record.changed_count,
                missing=record.missing_count,
                ignored=record.ignored_count,
                issues=record.issue_count,
            ),
            terminal_error_code=record.terminal_error_code,
            terminal_error_message=record.terminal_error_message,
        )
    except (ScanDomainError, ValueError, OverflowError) as error:
        raise PersistenceConversionError(f"scan run {record.id!r} is invalid") from error


def scan_issue_to_record(issue: ScanIssue) -> ScanIssueRecord:
    return ScanIssueRecord(
        id=issue.id.value,
        run_id=issue.run_id.value,
        media_file_id=None if issue.media_file_id is None else issue.media_file_id.value,
        relative_locator=issue.relative_locator,
        deduplication_key=issue.deduplication_key,
        code=issue.code,
        message=issue.message,
        severity=issue.severity.value,
        occurred_utc_us=datetime_to_epoch_microseconds(issue.occurred_utc),
    )


def scan_issue_from_record(record: ScanIssueRecord) -> ScanIssue:
    try:
        return ScanIssue(
            id=ScanIssueId(record.id),
            run_id=ScanRunId(record.run_id),
            media_file_id=(
                None if record.media_file_id is None else MediaFileId(record.media_file_id)
            ),
            relative_locator=record.relative_locator,
            deduplication_key=record.deduplication_key,
            code=record.code,
            message=record.message,
            severity=ScanIssueSeverity(record.severity),
            occurred_utc=epoch_microseconds_to_datetime(record.occurred_utc_us),
        )
    except (ScanDomainError, ValueError, OverflowError) as error:
        raise PersistenceConversionError(f"scan issue {record.id!r} is invalid") from error


def _optional_encode(value: datetime | None) -> int | None:
    return None if value is None else datetime_to_epoch_microseconds(value)


def _optional_decode(value: int | None) -> datetime | None:
    return None if value is None else epoch_microseconds_to_datetime(value)
