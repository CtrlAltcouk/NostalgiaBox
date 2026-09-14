"""Pure Phase 3 catalogue identity and playable-rendition values."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from itertools import pairwise

from nostalgiabox.domain.exceptions import InvalidIdentifierError


class CatalogueDomainError(Exception):
    """Base class for catalogue-domain invariant failures."""


class InvalidMediaFileError(CatalogueDomainError):
    """A physical media-file value has an invalid source-relative locator."""


class InvalidPlayableRenditionError(CatalogueDomainError):
    """A playable rendition has invalid segment or duration values."""


class RenditionOverlapError(CatalogueDomainError):
    """Independently playable ranges overlap on one physical file."""


class PreferredRenditionConflictError(CatalogueDomainError):
    """A catalogue item has more than one preferred rendition."""


class InvalidMediaSourceError(CatalogueDomainError):
    """A configured media source violates a lifecycle invariant."""


def _require_identifier(value: str, name: str) -> None:
    if not value.strip():
        raise InvalidIdentifierError(f"{name} must not be empty")


@dataclass(frozen=True, slots=True)
class CatalogueItemId:
    """Stable logical catalogue identity independent of files and paths."""

    value: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "CatalogueItemId")


@dataclass(frozen=True, slots=True)
class MediaSourceId:
    """Stable identity of one configured media source."""

    value: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "MediaSourceId")


@dataclass(frozen=True, slots=True)
class MediaFileId:
    """Stable identity of one observed physical file independent of locator."""

    value: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "MediaFileId")


@dataclass(frozen=True, slots=True)
class PlayableRenditionId:
    """Stable identity of one catalogue-to-file playable relationship."""

    value: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "PlayableRenditionId")


class MediaSourceKind(StrEnum):
    """Source technologies admitted by the Phase 3 foundation."""

    LOCAL = "local"
    SMB = "smb"


class SourceAvailability(StrEnum):
    """Latest structured availability result, independent of enabled state."""

    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    PERMISSION_DENIED = "permission_denied"
    INVALID_ROOT = "invalid_root"
    ERROR = "error"


class FilePresenceState(StrEnum):
    """Scanner classification without implying physical deletion or retirement."""

    UNCLASSIFIED = "unclassified"
    PRESENT = "present"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class CatalogueItem:
    """A stable logical programme identity that may not yet be playable."""

    id: CatalogueItemId


@dataclass(frozen=True, slots=True)
class MediaSource:
    """Stable source configuration, lifecycle and sanitized availability state."""

    id: MediaSourceId
    kind: MediaSourceKind
    display_name: str | None = None
    configured_root: str | None = None
    enabled: bool = False
    availability: SourceAvailability = SourceAvailability.UNKNOWN
    last_checked_utc: datetime | None = None
    last_successful_scan_utc: datetime | None = None
    current_error_code: str | None = None
    current_error_message: str | None = None
    retired_utc: datetime | None = None
    revision: int = 1

    def __post_init__(self) -> None:
        if self.display_name is not None and not self.display_name.strip():
            raise InvalidMediaSourceError("media-source display name must not be blank")
        if self.configured_root is not None:
            if not self.configured_root.strip():
                raise InvalidMediaSourceError("media-source configured root must not be blank")
            if "\x00" in self.configured_root:
                raise InvalidMediaSourceError("media-source configured root contains NUL")
        if self.revision < 1:
            raise InvalidMediaSourceError("media-source revision must be positive")
        if self.retired_utc is not None and self.enabled:
            raise InvalidMediaSourceError("a retired media source must be disabled")
        if (self.current_error_code is None) != (self.current_error_message is None):
            raise InvalidMediaSourceError(
                "media-source error code and message must both be present or absent"
            )
        if self.current_error_code is not None and not self.current_error_code.strip():
            raise InvalidMediaSourceError("media-source error code must not be blank")
        if self.current_error_message is not None and not self.current_error_message.strip():
            raise InvalidMediaSourceError("media-source error message must not be blank")
        for name, value in (
            ("last checked", self.last_checked_utc),
            ("last successful scan", self.last_successful_scan_utc),
            ("retired", self.retired_utc),
        ):
            if value is not None and (
                value.utcoffset() is None or value.utcoffset() != timedelta()
            ):
                raise InvalidMediaSourceError(f"media-source {name} timestamp must be aware UTC")


@dataclass(frozen=True, slots=True)
class MediaFile:
    """One physical file identified independently of its current relative locator."""

    id: MediaFileId
    source_id: MediaSourceId
    normalized_relative_locator: str
    original_relative_locator: str
    presence: FilePresenceState = FilePresenceState.UNCLASSIFIED
    size_bytes: int | None = None
    modified_time_ns: int | None = None
    device_id: int | None = None
    inode_id: int | None = None
    last_seen_generation: int | None = None
    first_observed_utc: datetime | None = None
    last_observed_utc: datetime | None = None
    missing_since_utc: datetime | None = None

    def __post_init__(self) -> None:
        _require_relative_locator(self.normalized_relative_locator, normalized=True)
        _require_relative_locator(self.original_relative_locator, normalized=False)
        observation_values = (
            self.size_bytes,
            self.modified_time_ns,
            self.last_seen_generation,
            self.first_observed_utc,
            self.last_observed_utc,
        )
        if self.presence is FilePresenceState.UNCLASSIFIED:
            if any(value is not None for value in observation_values) or any(
                value is not None
                for value in (self.device_id, self.inode_id, self.missing_since_utc)
            ):
                raise InvalidMediaFileError(
                    "unclassified media file must not contain fabricated scanner observations"
                )
            return
        if any(value is None for value in observation_values):
            raise InvalidMediaFileError(
                "classified media file requires a complete cheap observation"
            )
        if self.size_bytes is not None and self.size_bytes < 0:
            raise InvalidMediaFileError("media-file size must not be negative")
        if self.last_seen_generation is not None and self.last_seen_generation < 1:
            raise InvalidMediaFileError("media-file seen generation must be positive")
        for name, value in (
            ("first observed", self.first_observed_utc),
            ("last observed", self.last_observed_utc),
            ("missing since", self.missing_since_utc),
        ):
            if value is not None and (
                value.utcoffset() is None or value.utcoffset() != timedelta()
            ):
                raise InvalidMediaFileError(f"media-file {name} timestamp must be aware UTC")
        if (
            self.first_observed_utc is not None
            and self.last_observed_utc is not None
            and self.last_observed_utc < self.first_observed_utc
        ):
            raise InvalidMediaFileError(
                "media-file last observation must not precede first observation"
            )
        if self.presence is FilePresenceState.PRESENT and self.missing_since_utc is not None:
            raise InvalidMediaFileError("present media file must not have a missing timestamp")
        if self.presence is FilePresenceState.MISSING and self.missing_since_utc is None:
            raise InvalidMediaFileError("missing media file requires a missing timestamp")


@dataclass(frozen=True, slots=True)
class PlayableRendition:
    """A whole-file or bounded segment that can represent one catalogue item."""

    id: PlayableRenditionId
    catalogue_item_id: CatalogueItemId
    media_file_id: MediaFileId
    segment_start: timedelta
    segment_duration: timedelta
    logical_playable_duration: timedelta
    is_whole_file: bool
    preferred: bool = False

    def __post_init__(self) -> None:
        if self.segment_start < timedelta():
            raise InvalidPlayableRenditionError("segment start must not be negative")
        if self.segment_duration <= timedelta():
            raise InvalidPlayableRenditionError("segment duration must be greater than zero")
        if self.logical_playable_duration <= timedelta():
            raise InvalidPlayableRenditionError(
                "logical playable duration must be greater than zero"
            )
        if self.logical_playable_duration > self.segment_duration:
            raise InvalidPlayableRenditionError(
                "logical playable duration must not exceed segment duration"
            )
        if self.is_whole_file and self.segment_start != timedelta():
            raise InvalidPlayableRenditionError("whole-file rendition must start at zero")
        if self.is_whole_file and self.logical_playable_duration != self.segment_duration:
            raise InvalidPlayableRenditionError(
                "whole-file logical duration must equal segment duration"
            )
        try:
            self.segment_start + self.segment_duration
        except OverflowError as error:
            raise InvalidPlayableRenditionError("segment end is outside timedelta range") from error

    @property
    def segment_end(self) -> timedelta:
        """Return the exact exclusive physical end of this playable range."""
        return self.segment_start + self.segment_duration


def validate_physical_duration(
    rendition: PlayableRendition,
    measured_physical_duration: timedelta,
) -> None:
    """Require a rendition to fit a supplied measured physical-file duration."""
    if measured_physical_duration <= timedelta():
        raise InvalidPlayableRenditionError("measured physical duration must be greater than zero")
    if rendition.segment_end > measured_physical_duration:
        raise InvalidPlayableRenditionError(
            "rendition segment end exceeds measured physical duration"
        )


def validate_rendition_set(renditions: tuple[PlayableRendition, ...]) -> None:
    """Validate cross-row preferred and default non-overlap policies."""
    preferred_catalogue_ids: set[CatalogueItemId] = set()
    ranges_by_file: dict[MediaFileId, list[PlayableRendition]] = {}

    for rendition in renditions:
        if rendition.preferred:
            if rendition.catalogue_item_id in preferred_catalogue_ids:
                raise PreferredRenditionConflictError(
                    f"catalogue item {rendition.catalogue_item_id.value!r} "
                    "has more than one preferred rendition"
                )
            preferred_catalogue_ids.add(rendition.catalogue_item_id)
        ranges_by_file.setdefault(rendition.media_file_id, []).append(rendition)

    for media_file_id, file_renditions in ranges_by_file.items():
        ordered = sorted(file_renditions, key=lambda value: value.segment_start)
        for previous, current in pairwise(ordered):
            if current.segment_start < previous.segment_end:
                raise RenditionOverlapError(
                    f"renditions {previous.id.value!r} and {current.id.value!r} overlap "
                    f"on media file {media_file_id.value!r}"
                )


def _require_relative_locator(value: str, *, normalized: bool) -> None:
    if not value or not value.strip():
        raise InvalidMediaFileError("media-file relative locator must not be empty")
    if value != value.strip() or "\x00" in value:
        raise InvalidMediaFileError("media-file relative locator contains invalid characters")
    if value.startswith(("/", "\\")):
        raise InvalidMediaFileError("media-file locator must be source-relative")
    if len(value) >= 3 and value[0].isalpha() and value[1] == ":" and value[2] in {"/", "\\"}:
        raise InvalidMediaFileError("media-file locator must not be an absolute drive path")
    if normalized and "\\" in value:
        raise InvalidMediaFileError("normalized media-file locator must use forward slashes")
    segments = value.replace("\\", "/").split("/")
    if any(segment in {"", ".", ".."} for segment in segments):
        raise InvalidMediaFileError(
            "media-file locator must not contain empty or traversal segments"
        )
