"""Pure Phase 3 catalogue identity and playable-rendition values."""

from dataclasses import dataclass
from datetime import timedelta
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


@dataclass(frozen=True, slots=True)
class CatalogueItem:
    """A stable logical programme identity that may not yet be playable."""

    id: CatalogueItemId


@dataclass(frozen=True, slots=True)
class MediaSource:
    """Minimum source identity/type foundation; lifecycle belongs to Task 3.2."""

    id: MediaSourceId
    kind: MediaSourceKind


@dataclass(frozen=True, slots=True)
class MediaFile:
    """One physical file identified independently of its current relative locator."""

    id: MediaFileId
    source_id: MediaSourceId
    normalized_relative_locator: str
    original_relative_locator: str

    def __post_init__(self) -> None:
        _require_relative_locator(self.normalized_relative_locator, normalized=True)
        _require_relative_locator(self.original_relative_locator, normalized=False)


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
