"""SQLAlchemy adapters for durable scan runs, inventory and issues."""

from datetime import datetime

from sqlalchemy import exists, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nostalgiabox.application.scans import ScanAlreadyRunningError
from nostalgiabox.domain.catalogue import (
    FilePresenceState,
    MediaFile,
    MediaSourceId,
)
from nostalgiabox.domain.scanning import (
    ScanIssue,
    ScanRun,
    ScanRunId,
    ScanStatus,
    validate_scan_transition,
)
from nostalgiabox.persistence.catalogue_mappers import (
    media_file_from_record,
    media_file_to_record,
)
from nostalgiabox.persistence.codecs import datetime_to_epoch_microseconds
from nostalgiabox.persistence.models import MediaFileRecord, ScanIssueRecord, ScanRunRecord
from nostalgiabox.persistence.scan_mappers import (
    scan_issue_from_record,
    scan_issue_to_record,
    scan_run_from_record,
    scan_run_to_record,
)


class SqlAlchemyScanRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, run: ScanRun) -> None:
        self._session.add(scan_run_to_record(run))
        try:
            self._session.flush()
        except IntegrityError as error:
            raise ScanAlreadyRunningError(
                f"source {run.source_id.value!r} already has an active scan or generation"
            ) from error

    def get(self, run_id: ScanRunId) -> ScanRun | None:
        record = self._session.get(ScanRunRecord, run_id.value)
        return None if record is None else scan_run_from_record(record)

    def update(self, run: ScanRun) -> None:
        record = self._session.get(ScanRunRecord, run.id.value)
        if record is None:
            raise RuntimeError(f"scan run {run.id.value!r} does not exist")
        validate_scan_transition(ScanStatus(record.status), run.status)
        encoded = scan_run_to_record(run)
        for name in (
            "source_id",
            "kind",
            "generation",
            "status",
            "cancellation_requested",
            "queued_utc_us",
            "started_utc_us",
            "finished_utc_us",
            "source_revision",
            "source_root",
            "discovered_count",
            "added_count",
            "unchanged_count",
            "changed_count",
            "missing_count",
            "ignored_count",
            "issue_count",
            "terminal_error_code",
            "terminal_error_message",
        ):
            setattr(record, name, getattr(encoded, name))

    def next_generation(self, source_id: MediaSourceId) -> int:
        current = self._session.scalar(
            select(func.max(ScanRunRecord.generation)).where(
                ScanRunRecord.source_id == source_id.value
            )
        )
        return 1 if current is None else current + 1

    def has_active(self, source_id: MediaSourceId) -> bool:
        return bool(
            self._session.scalar(
                select(
                    exists().where(
                        ScanRunRecord.source_id == source_id.value,
                        ScanRunRecord.status.in_(
                            (ScanStatus.QUEUED.value, ScanStatus.RUNNING.value)
                        ),
                    )
                )
            )
        )

    def list_active(self) -> tuple[ScanRun, ...]:
        records = self._session.scalars(
            select(ScanRunRecord)
            .where(ScanRunRecord.status.in_((ScanStatus.QUEUED.value, ScanStatus.RUNNING.value)))
            .order_by(ScanRunRecord.queued_utc_us, ScanRunRecord.id)
        ).all()
        return tuple(scan_run_from_record(record) for record in records)


class SqlAlchemyMediaInventoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_present(self, source_id: MediaSourceId, normalized_locator: str) -> MediaFile | None:
        record = self._session.scalar(
            select(MediaFileRecord).where(
                MediaFileRecord.source_id == source_id.value,
                MediaFileRecord.normalized_relative_locator == normalized_locator,
                MediaFileRecord.presence == FilePresenceState.PRESENT.value,
            )
        )
        return None if record is None else media_file_from_record(record)

    def list_missing(
        self, source_id: MediaSourceId, normalized_locator: str
    ) -> tuple[MediaFile, ...]:
        return self._list_by_presence(source_id, normalized_locator, FilePresenceState.MISSING)

    def list_unclassified(
        self, source_id: MediaSourceId, normalized_locator: str
    ) -> tuple[MediaFile, ...]:
        return self._list_by_presence(source_id, normalized_locator, FilePresenceState.UNCLASSIFIED)

    def store(self, media_file: MediaFile) -> None:
        record = self._session.get(MediaFileRecord, media_file.id.value)
        encoded = media_file_to_record(media_file)
        if record is None:
            self._session.add(encoded)
            return
        for name in (
            "source_id",
            "normalized_relative_locator",
            "original_relative_locator",
            "presence",
            "size_bytes",
            "modified_time_ns",
            "device_id",
            "inode_id",
            "last_seen_generation",
            "first_observed_utc_us",
            "last_observed_utc_us",
            "missing_since_utc_us",
        ):
            setattr(record, name, getattr(encoded, name))

    def mark_unseen_missing(
        self,
        source_id: MediaSourceId,
        generation: int,
        missing_utc: datetime,
    ) -> int:
        result = self._session.execute(
            update(MediaFileRecord)
            .where(
                MediaFileRecord.source_id == source_id.value,
                MediaFileRecord.presence == FilePresenceState.PRESENT.value,
                (
                    (MediaFileRecord.last_seen_generation.is_(None))
                    | (MediaFileRecord.last_seen_generation != generation)
                ),
            )
            .values(
                presence=FilePresenceState.MISSING.value,
                missing_since_utc_us=datetime_to_epoch_microseconds(missing_utc),
            )
        )
        return result.rowcount

    def _list_by_presence(
        self,
        source_id: MediaSourceId,
        normalized_locator: str,
        presence: FilePresenceState,
    ) -> tuple[MediaFile, ...]:
        records = self._session.scalars(
            select(MediaFileRecord)
            .where(
                MediaFileRecord.source_id == source_id.value,
                MediaFileRecord.normalized_relative_locator == normalized_locator,
                MediaFileRecord.presence == presence.value,
            )
            .order_by(MediaFileRecord.id)
        ).all()
        return tuple(media_file_from_record(record) for record in records)


class SqlAlchemyScanIssueRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, issue: ScanIssue) -> bool:
        if any(
            isinstance(record, ScanIssueRecord)
            and record.run_id == issue.run_id.value
            and record.deduplication_key == issue.deduplication_key
            for record in self._session.new
        ):
            return False
        exists_record = self._session.scalar(
            select(
                exists().where(
                    ScanIssueRecord.run_id == issue.run_id.value,
                    ScanIssueRecord.deduplication_key == issue.deduplication_key,
                )
            )
        )
        if exists_record:
            return False
        self._session.add(scan_issue_to_record(issue))
        return True

    def list_for_run(self, run_id: ScanRunId) -> tuple[ScanIssue, ...]:
        records = self._session.scalars(
            select(ScanIssueRecord)
            .where(ScanIssueRecord.run_id == run_id.value)
            .order_by(ScanIssueRecord.occurred_utc_us, ScanIssueRecord.id)
        ).all()
        return tuple(scan_issue_from_record(record) for record in records)
