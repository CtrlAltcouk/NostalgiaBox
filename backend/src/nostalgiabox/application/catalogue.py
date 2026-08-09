"""Application ports and playback projection for the Phase 3 catalogue foundation."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from nostalgiabox.domain.catalogue import (
    CatalogueItem,
    CatalogueItemId,
    MediaFile,
    MediaFileId,
    MediaSource,
    MediaSourceId,
    PlayableRendition,
    PlayableRenditionId,
)


@dataclass(frozen=True, slots=True)
class CataloguePlaybackProjection:
    """Resolved physical playback facts kept outside timeline and UI concerns."""

    catalogue_item_id: CatalogueItemId
    physical_path: str
    segment_start: timedelta
    segment_duration: timedelta
    logical_playable_duration: timedelta

    def __post_init__(self) -> None:
        if not self.physical_path.strip():
            raise ValueError("catalogue playback physical path must not be empty")
        if self.segment_start < timedelta():
            raise ValueError("catalogue playback segment start must not be negative")
        if self.segment_duration <= timedelta():
            raise ValueError("catalogue playback segment duration must be greater than zero")
        if self.logical_playable_duration <= timedelta():
            raise ValueError("catalogue playback logical duration must be greater than zero")
        if self.logical_playable_duration > self.segment_duration:
            raise ValueError("catalogue playback logical duration exceeds segment duration")

    @classmethod
    def from_rendition(
        cls,
        rendition: PlayableRendition,
        physical_path: str,
    ) -> "CataloguePlaybackProjection":
        """Build a projection after infrastructure resolves the physical path."""
        return cls(
            catalogue_item_id=rendition.catalogue_item_id,
            physical_path=physical_path,
            segment_start=rendition.segment_start,
            segment_duration=rendition.segment_duration,
            logical_playable_duration=rendition.logical_playable_duration,
        )

    @property
    def segment_end(self) -> timedelta:
        """Return the exclusive physical segment end."""
        return self.segment_start + self.segment_duration

    def physical_position(self, logical_offset: timedelta) -> timedelta:
        """Translate a validated logical offset without changing timeline truth."""
        if logical_offset < timedelta() or logical_offset >= self.logical_playable_duration:
            raise ValueError("logical playback offset is outside playable duration")
        return self.segment_start + logical_offset


class CatalogueItemRepository(Protocol):
    """Caller-transaction-owned persistence port for logical catalogue identities."""

    def store(self, item: CatalogueItem) -> None: ...

    def get_by_id(self, item_id: CatalogueItemId) -> CatalogueItem | None: ...


class MediaSourceRepository(Protocol):
    """Caller-transaction-owned persistence port for source identities."""

    def store(self, source: MediaSource) -> None: ...

    def get_by_id(self, source_id: MediaSourceId) -> MediaSource | None: ...


class MediaFileRepository(Protocol):
    """Caller-transaction-owned persistence port for physical-file identities."""

    def store(self, media_file: MediaFile) -> None: ...

    def get_by_id(self, media_file_id: MediaFileId) -> MediaFile | None: ...


class PlayableRenditionRepository(Protocol):
    """Caller-transaction-owned persistence port for playable ranges."""

    def store(self, rendition: PlayableRendition) -> None: ...

    def get_by_id(self, rendition_id: PlayableRenditionId) -> PlayableRendition | None: ...

    def list_for_catalogue_item(
        self, item_id: CatalogueItemId
    ) -> tuple[PlayableRendition, ...]: ...

    def get_preferred(self, item_id: CatalogueItemId) -> PlayableRendition | None: ...


class PlayableProjectionResolver(Protocol):
    """Resolve a catalogue identity without exposing persistence or path selection to clients."""

    def resolve(self, item_id: CatalogueItemId) -> CataloguePlaybackProjection | None: ...
