"""Pure durable scan-run and filesystem-observation values."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from unicodedata import normalize

from nostalgiabox.domain.catalogue import MediaFileId, MediaSourceId
from nostalgiabox.domain.exceptions import InvalidIdentifierError


class ScanDomainError(Exception):
    """Base class for scanner-domain invariant failures."""


class InvalidScanRunError(ScanDomainError):
    """A durable scan run violates its state-machine invariants."""


class InvalidScanObservationError(ScanDomainError):
    """A filesystem observation is malformed or unsafe."""


class InvalidScanIssueError(ScanDomainError):
    """A structured issue contains unsafe or incomplete values."""


class InvalidScanTransitionError(ScanDomainError):
    """A scan status transition is not permitted by the durable state machine."""


@dataclass(frozen=True, slots=True)
class ScanRunId:
    value: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "ScanRunId")


@dataclass(frozen=True, slots=True)
class ScanIssueId:
    value: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "ScanIssueId")


class ScanKind(StrEnum):
    FULL = "full"
    INCREMENTAL = "incremental"


class ScanStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    FAILED = "failed"

    @property
    def is_active(self) -> bool:
        return self in {ScanStatus.QUEUED, ScanStatus.RUNNING}

    @property
    def is_terminal(self) -> bool:
        return not self.is_active


class ScanIssueSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScanCounters:
    discovered: int = 0
    added: int = 0
    unchanged: int = 0
    changed: int = 0
    missing: int = 0
    ignored: int = 0
    issues: int = 0

    def __post_init__(self) -> None:
        if any(
            value < 0
            for value in (
                self.discovered,
                self.added,
                self.unchanged,
                self.changed,
                self.missing,
                self.ignored,
                self.issues,
            )
        ):
            raise InvalidScanRunError("scan counters must not be negative")
        if self.added + self.unchanged + self.changed > self.discovered:
            raise InvalidScanRunError("scan outcome counters exceed discovered count")

    def plus(
        self,
        *,
        discovered: int = 0,
        added: int = 0,
        unchanged: int = 0,
        changed: int = 0,
        missing: int = 0,
        ignored: int = 0,
        issues: int = 0,
    ) -> "ScanCounters":
        return ScanCounters(
            discovered=self.discovered + discovered,
            added=self.added + added,
            unchanged=self.unchanged + unchanged,
            changed=self.changed + changed,
            missing=self.missing + missing,
            ignored=self.ignored + ignored,
            issues=self.issues + issues,
        )


@dataclass(frozen=True, slots=True)
class ScanRun:
    id: ScanRunId
    source_id: MediaSourceId
    kind: ScanKind
    generation: int
    status: ScanStatus
    cancellation_requested: bool
    queued_utc: datetime
    started_utc: datetime | None = None
    finished_utc: datetime | None = None
    source_revision: int | None = None
    source_root: str | None = None
    counters: ScanCounters = ScanCounters()
    terminal_error_code: str | None = None
    terminal_error_message: str | None = None

    def __post_init__(self) -> None:
        if self.generation < 1:
            raise InvalidScanRunError("scan generation must be positive")
        _require_utc(self.queued_utc, "queued")
        for name, value in (("started", self.started_utc), ("finished", self.finished_utc)):
            if value is not None:
                _require_utc(value, name)
        if self.started_utc is not None and self.started_utc < self.queued_utc:
            raise InvalidScanRunError("scan start must not precede queue time")
        if self.finished_utc is not None:
            baseline = self.started_utc or self.queued_utc
            if self.finished_utc < baseline:
                raise InvalidScanRunError("scan finish must not precede its active time")
        if self.status is ScanStatus.QUEUED and (
            self.started_utc is not None or self.finished_utc is not None
        ):
            raise InvalidScanRunError("queued scan must not have start or finish timestamps")
        if self.status is ScanStatus.RUNNING and (
            self.started_utc is None or self.finished_utc is not None
        ):
            raise InvalidScanRunError("running scan requires only a start timestamp")
        if self.status is ScanStatus.COMPLETED and (
            self.started_utc is None or self.finished_utc is None
        ):
            raise InvalidScanRunError("completed scan requires start and finish timestamps")
        if self.status.is_terminal and self.finished_utc is None:
            raise InvalidScanRunError("terminal scan requires a finish timestamp")
        if (self.source_revision is None) != (self.source_root is None):
            raise InvalidScanRunError("scan source revision and root snapshot must be paired")
        if self.source_revision is not None and self.source_revision < 1:
            raise InvalidScanRunError("scan source revision must be positive")
        if self.source_root is not None and not self.source_root.strip():
            raise InvalidScanRunError("scan source root snapshot must not be blank")
        if (self.terminal_error_code is None) != (self.terminal_error_message is None):
            raise InvalidScanRunError("scan terminal error code and message must be paired")
        if self.terminal_error_code is not None and not self.terminal_error_code.strip():
            raise InvalidScanRunError("scan terminal error code must not be blank")
        if self.terminal_error_message is not None and not self.terminal_error_message.strip():
            raise InvalidScanRunError("scan terminal error message must not be blank")
        if self.status in {ScanStatus.QUEUED, ScanStatus.RUNNING, ScanStatus.COMPLETED} and (
            self.terminal_error_code is not None
        ):
            raise InvalidScanRunError("non-failed scan state must not contain terminal error")


@dataclass(frozen=True, slots=True)
class MediaFileObservation:
    normalized_relative_locator: str
    original_relative_locator: str
    size_bytes: int
    modified_time_ns: int
    device_id: int | None = None
    inode_id: int | None = None

    def __post_init__(self) -> None:
        _require_locator(self.normalized_relative_locator, normalized=True)
        _require_locator(self.original_relative_locator, normalized=False)
        if self.normalized_relative_locator != normalize("NFC", self.normalized_relative_locator):
            raise InvalidScanObservationError("normalized observation locator must use Unicode NFC")
        if self.size_bytes < 0:
            raise InvalidScanObservationError("observation size must not be negative")
        if self.device_id is not None and self.device_id < 0:
            raise InvalidScanObservationError("observation device identifier must not be negative")
        if self.inode_id is not None and self.inode_id < 0:
            raise InvalidScanObservationError("observation inode identifier must not be negative")

    @property
    def cheap_signature(self) -> tuple[str, int, int]:
        return (self.normalized_relative_locator, self.size_bytes, self.modified_time_ns)


@dataclass(frozen=True, slots=True)
class ScanIssue:
    id: ScanIssueId
    run_id: ScanRunId
    deduplication_key: str
    code: str
    message: str
    occurred_utc: datetime
    severity: ScanIssueSeverity
    media_file_id: MediaFileId | None = None
    relative_locator: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("deduplication key", self.deduplication_key),
            ("code", self.code),
            ("message", self.message),
        ):
            if not value.strip():
                raise InvalidScanIssueError(f"scan issue {name} must not be blank")
        _require_utc(self.occurred_utc, "issue occurrence")
        if self.relative_locator is not None:
            _require_locator(self.relative_locator, normalized=True)


def validate_scan_transition(previous: ScanStatus, current: ScanStatus) -> None:
    """Allow progress updates in-place and only the approved forward state transitions."""
    allowed = {
        ScanStatus.QUEUED: {
            ScanStatus.QUEUED,
            ScanStatus.RUNNING,
            ScanStatus.CANCELLED,
            ScanStatus.INTERRUPTED,
            ScanStatus.FAILED,
        },
        ScanStatus.RUNNING: {
            ScanStatus.RUNNING,
            ScanStatus.COMPLETED,
            ScanStatus.CANCELLED,
            ScanStatus.INTERRUPTED,
            ScanStatus.FAILED,
        },
        ScanStatus.COMPLETED: {ScanStatus.COMPLETED},
        ScanStatus.CANCELLED: {ScanStatus.CANCELLED},
        ScanStatus.INTERRUPTED: {ScanStatus.INTERRUPTED},
        ScanStatus.FAILED: {ScanStatus.FAILED},
    }
    if current not in allowed[previous]:
        raise InvalidScanTransitionError(
            f"scan status cannot transition from {previous.value} to {current.value}"
        )


def _require_identifier(value: str, name: str) -> None:
    if not value.strip():
        raise InvalidIdentifierError(f"{name} must not be empty")


def _require_utc(value: datetime, name: str) -> None:
    if value.utcoffset() is None or value.utcoffset() != timedelta():
        raise InvalidScanRunError(f"scan {name} timestamp must be aware UTC")


def _require_locator(value: str, *, normalized: bool) -> None:
    if not value or value != value.strip() or "\x00" in value:
        raise InvalidScanObservationError("observation locator is malformed")
    if value.startswith(("/", "\\")):
        raise InvalidScanObservationError("observation locator must be source-relative")
    if normalized and "\\" in value:
        raise InvalidScanObservationError("normalized observation locator must use forward slashes")
    parts = value.replace("\\", "/").split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise InvalidScanObservationError("observation locator contains traversal")
