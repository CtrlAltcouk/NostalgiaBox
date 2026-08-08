"""Immutable core values used by the timeline engine."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from nostalgiabox.domain.exceptions import (
    InvalidChannelError,
    InvalidIdentifierError,
    InvalidMediaItemError,
    InvalidTimelineEntryError,
)
from nostalgiabox.domain.time import normalize_utc


def _require_identifier(value: str, identifier_name: str) -> None:
    if not value.strip():
        raise InvalidIdentifierError(f"{identifier_name} must not be empty")


@dataclass(frozen=True, slots=True)
class MediaItemId:
    """Stable identity of a media item independent of its display title."""

    value: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "MediaItemId")


@dataclass(frozen=True, slots=True)
class ChannelId:
    """Stable identity of a channel independent of its channel number."""

    value: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "ChannelId")


@dataclass(frozen=True, slots=True)
class TimelineEntryId:
    """Stable deterministic identity of a timeline entry."""

    value: str

    def __post_init__(self) -> None:
        _require_identifier(self.value, "TimelineEntryId")


class ContentKind(StrEnum):
    """Kind of content occupying a timeline interval."""

    PROGRAMME = "programme"


@dataclass(frozen=True, slots=True)
class MediaItem:
    """Media metadata required for deterministic timeline construction."""

    id: MediaItemId
    title: str
    duration: timedelta

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise InvalidMediaItemError("media item title must not be empty")
        if self.duration <= timedelta(0):
            raise InvalidMediaItemError("media item duration must be greater than zero")


@dataclass(frozen=True, slots=True)
class Channel:
    """Minimum channel identity required by the one-channel proof."""

    id: ChannelId
    number: int
    name: str

    def __post_init__(self) -> None:
        if self.number <= 0:
            raise InvalidChannelError("channel number must be greater than zero")
        if not self.name.strip():
            raise InvalidChannelError("channel name must not be empty")


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    """One immutable half-open UTC interval on a channel timeline."""

    id: TimelineEntryId
    channel_id: ChannelId
    media_item_id: MediaItemId
    content_kind: ContentKind
    start_utc: datetime
    end_utc: datetime

    def __post_init__(self) -> None:
        start_utc = normalize_utc(self.start_utc, field_name="timeline entry start")
        end_utc = normalize_utc(self.end_utc, field_name="timeline entry end")
        if end_utc <= start_utc:
            raise InvalidTimelineEntryError("timeline entry end must be after its start")
        object.__setattr__(self, "start_utc", start_utc)
        object.__setattr__(self, "end_utc", end_utc)

    @property
    def duration(self) -> timedelta:
        """Return the exact interval duration at datetime microsecond precision."""
        return self.end_utc - self.start_utc
