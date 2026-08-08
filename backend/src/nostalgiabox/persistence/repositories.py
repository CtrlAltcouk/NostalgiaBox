"""Small SQLAlchemy repositories returning approved non-ORM values."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from nostalgiabox.domain.models import Channel, ChannelId, MediaItemId
from nostalgiabox.domain.timeline import ChannelTimeline
from nostalgiabox.persistence.codecs import timedelta_to_microseconds
from nostalgiabox.persistence.errors import RecordNotFoundError
from nostalgiabox.persistence.mappers import (
    channel_from_record,
    channel_to_record,
    media_from_record,
    media_to_record,
    timeline_entry_from_record,
    timeline_entry_to_record,
)
from nostalgiabox.persistence.media import StoredMediaItem
from nostalgiabox.persistence.models import ChannelRecord, MediaItemRecord, TimelineEntryRecord


class MediaRepository:
    """Store and retrieve media while keeping paths outside domain objects."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def store(self, stored_media: StoredMediaItem) -> None:
        """Insert or update media by stable domain identity without committing."""
        record = self._session.get(MediaItemRecord, stored_media.media_item.id.value)
        if record is None:
            self._session.add(media_to_record(stored_media))
            return
        record.title = stored_media.media_item.title
        record.duration_us = timedelta_to_microseconds(stored_media.media_item.duration)
        record.path = stored_media.path

    def get_by_id(self, media_id: MediaItemId) -> StoredMediaItem | None:
        """Return stored media or ``None`` when the ID is absent."""
        record = self._session.get(MediaItemRecord, media_id.value)
        return None if record is None else media_from_record(record)


class ChannelRepository:
    """Store and retrieve channels by stable ID or unique number."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def store(self, channel: Channel) -> None:
        """Insert or update a channel by stable identity without committing."""
        record = self._session.get(ChannelRecord, channel.id.value)
        if record is None:
            self._session.add(channel_to_record(channel))
            return
        record.number = channel.number
        record.name = channel.name

    def get_by_id(self, channel_id: ChannelId) -> Channel | None:
        """Return a channel or ``None`` when the ID is absent."""
        record = self._session.get(ChannelRecord, channel_id.value)
        return None if record is None else channel_from_record(record)

    def get_by_number(self, channel_number: int) -> Channel | None:
        """Return the uniquely numbered channel or ``None`` when absent."""
        record = self._session.scalar(
            select(ChannelRecord).where(ChannelRecord.number == channel_number)
        )
        return None if record is None else channel_from_record(record)


class TimelineRepository:
    """Replace and reconstruct complete validated channel timelines."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def replace(self, timeline: ChannelTimeline) -> None:
        """Replace only one channel's entries without committing the transaction."""
        self._session.execute(
            delete(TimelineEntryRecord).where(
                TimelineEntryRecord.channel_id == timeline.channel.id.value
            )
        )
        self._session.add_all(timeline_entry_to_record(entry) for entry in timeline.entries)

    def load(self, channel_id: ChannelId) -> ChannelTimeline:
        """Load an ordered timeline or raise an explicit not-found error."""
        channel_record = self._session.get(ChannelRecord, channel_id.value)
        if channel_record is None:
            raise RecordNotFoundError(f"channel {channel_id.value!r} was not found")

        records = self._session.scalars(
            select(TimelineEntryRecord)
            .where(TimelineEntryRecord.channel_id == channel_id.value)
            .order_by(TimelineEntryRecord.start_utc_us)
        ).all()
        if not records:
            raise RecordNotFoundError(f"channel {channel_id.value!r} has no persisted timeline")

        return ChannelTimeline(
            channel=channel_from_record(channel_record),
            entries=tuple(timeline_entry_from_record(record) for record in records),
        )
