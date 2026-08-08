"""Explicit conversion boundary between ORM records and domain values."""

from nostalgiabox.domain.exceptions import TimelineDomainError
from nostalgiabox.domain.models import (
    Channel,
    ChannelId,
    ContentKind,
    MediaItem,
    MediaItemId,
    TimelineEntry,
    TimelineEntryId,
)
from nostalgiabox.persistence.codecs import (
    datetime_to_epoch_microseconds,
    epoch_microseconds_to_datetime,
    microseconds_to_timedelta,
    timedelta_to_microseconds,
)
from nostalgiabox.persistence.errors import (
    InvalidStoredMediaError,
    PersistenceConversionError,
    UnknownContentKindError,
)
from nostalgiabox.persistence.media import StoredMediaItem
from nostalgiabox.persistence.models import ChannelRecord, MediaItemRecord, TimelineEntryRecord


def media_to_record(stored_media: StoredMediaItem) -> MediaItemRecord:
    """Convert stored media to a new ORM record."""
    media = stored_media.media_item
    return MediaItemRecord(
        id=media.id.value,
        title=media.title,
        duration_us=timedelta_to_microseconds(media.duration),
        path=stored_media.path,
    )


def media_from_record(record: MediaItemRecord) -> StoredMediaItem:
    """Reconstruct stored media, rejecting corrupt persistence values."""
    try:
        media = MediaItem(
            id=MediaItemId(record.id),
            title=record.title,
            duration=microseconds_to_timedelta(record.duration_us),
        )
        return StoredMediaItem(media_item=media, path=record.path)
    except (TimelineDomainError, InvalidStoredMediaError) as error:
        raise PersistenceConversionError(
            f"media record {record.id!r} contains invalid persisted values"
        ) from error


def channel_to_record(channel: Channel) -> ChannelRecord:
    """Convert a domain channel to a new ORM record."""
    return ChannelRecord(id=channel.id.value, number=channel.number, name=channel.name)


def channel_from_record(record: ChannelRecord) -> Channel:
    """Reconstruct a domain channel, rejecting corrupt persistence values."""
    try:
        return Channel(id=ChannelId(record.id), number=record.number, name=record.name)
    except TimelineDomainError as error:
        raise PersistenceConversionError(
            f"channel record {record.id!r} contains invalid persisted values"
        ) from error


def timeline_entry_to_record(entry: TimelineEntry) -> TimelineEntryRecord:
    """Convert a domain timeline entry to a new ORM record."""
    return TimelineEntryRecord(
        id=entry.id.value,
        channel_id=entry.channel_id.value,
        media_item_id=entry.media_item_id.value,
        content_kind=entry.content_kind.value,
        start_utc_us=datetime_to_epoch_microseconds(entry.start_utc),
        end_utc_us=datetime_to_epoch_microseconds(entry.end_utc),
    )


def timeline_entry_from_record(record: TimelineEntryRecord) -> TimelineEntry:
    """Reconstruct a domain entry with explicit unknown-kind handling."""
    try:
        content_kind = ContentKind(record.content_kind)
    except ValueError as error:
        raise UnknownContentKindError(
            f"timeline entry {record.id!r} has unknown content kind {record.content_kind!r}"
        ) from error

    try:
        return TimelineEntry(
            id=TimelineEntryId(record.id),
            channel_id=ChannelId(record.channel_id),
            media_item_id=MediaItemId(record.media_item_id),
            content_kind=content_kind,
            start_utc=epoch_microseconds_to_datetime(record.start_utc_us),
            end_utc=epoch_microseconds_to_datetime(record.end_utc_us),
        )
    except (TimelineDomainError, OverflowError) as error:
        raise PersistenceConversionError(
            f"timeline entry record {record.id!r} contains invalid persisted values"
        ) from error
