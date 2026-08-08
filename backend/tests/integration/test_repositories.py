"""Behavioral tests for mappings, repositories and SQLite constraints."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nostalgiabox.domain import (
    Channel,
    ChannelId,
    ContentKind,
    MediaItem,
    MediaItemId,
    TimelineEntry,
    TimelineEntryId,
    build_sequential_timeline,
)
from nostalgiabox.persistence.errors import RecordNotFoundError
from nostalgiabox.persistence.media import StoredMediaItem
from nostalgiabox.persistence.models import TimelineEntryRecord
from nostalgiabox.persistence.repositories import (
    ChannelRepository,
    MediaRepository,
    TimelineRepository,
)

_START = datetime(2026, 8, 8, 18, 0, 0, 123456, tzinfo=UTC)


def test_media_channel_and_timeline_round_trip_exactly(persistence_session: Session) -> None:
    channel, stored_media = _proof_values()
    timeline = build_sequential_timeline(
        channel,
        _START,
        tuple(item.media_item for item in stored_media),
    )
    media_repository = MediaRepository(persistence_session)
    channel_repository = ChannelRepository(persistence_session)
    timeline_repository = TimelineRepository(persistence_session)

    for item in stored_media:
        media_repository.store(item)
    channel_repository.store(channel)
    timeline_repository.replace(timeline)
    persistence_session.flush()
    persistence_session.expire_all()

    assert media_repository.get_by_id(stored_media[0].media_item.id) == stored_media[0]
    assert channel_repository.get_by_id(channel.id) == channel
    assert channel_repository.get_by_number(channel.number) == channel
    assert timeline_repository.load(channel.id) == timeline
    assert [entry.start_utc for entry in timeline_repository.load(channel.id).entries] == [
        _START,
        _START + timedelta(microseconds=1_320_000_001),
    ]


def test_missing_repository_lookups_are_explicit(persistence_session: Session) -> None:
    assert MediaRepository(persistence_session).get_by_id(MediaItemId("missing")) is None
    assert ChannelRepository(persistence_session).get_by_id(ChannelId("missing")) is None
    assert ChannelRepository(persistence_session).get_by_number(999) is None
    with pytest.raises(RecordNotFoundError, match="was not found"):
        TimelineRepository(persistence_session).load(ChannelId("missing"))

    channel = Channel(ChannelId("channel-without-timeline"), 50, "No Timeline")
    ChannelRepository(persistence_session).store(channel)
    persistence_session.flush()
    with pytest.raises(RecordNotFoundError, match="has no persisted timeline"):
        TimelineRepository(persistence_session).load(channel.id)


def test_duplicate_channel_number_is_rejected(persistence_session: Session) -> None:
    repository = ChannelRepository(persistence_session)
    repository.store(Channel(ChannelId("channel-a"), 1, "A"))
    repository.store(Channel(ChannelId("channel-b"), 1, "B"))

    with pytest.raises(IntegrityError):
        persistence_session.flush()


def test_sqlite_rejects_orphan_timeline_entry(
    persistence_engine: Engine,
    persistence_session: Session,
) -> None:
    with persistence_engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1

    persistence_session.add(
        TimelineEntryRecord(
            id="orphan",
            channel_id="missing-channel",
            media_item_id="missing-media",
            content_kind="programme",
            start_utc_us=0,
            end_utc_us=1,
        )
    )

    with pytest.raises(IntegrityError):
        persistence_session.flush()


def test_timeline_record_preserves_all_fields(persistence_session: Session) -> None:
    channel, stored_media = _proof_values()
    media_repository = MediaRepository(persistence_session)
    media_repository.store(stored_media[0])
    ChannelRepository(persistence_session).store(channel)
    entry = TimelineEntry(
        id=TimelineEntryId("entry-exact"),
        channel_id=channel.id,
        media_item_id=stored_media[0].media_item.id,
        content_kind=ContentKind.PROGRAMME,
        start_utc=_START,
        end_utc=_START + timedelta(microseconds=1_000_001),
    )
    timeline = build_sequential_timeline(channel, _START, (stored_media[0].media_item,))
    exact_timeline = type(timeline)(channel=channel, entries=(entry,))

    TimelineRepository(persistence_session).replace(exact_timeline)
    persistence_session.flush()
    persistence_session.expire_all()

    assert TimelineRepository(persistence_session).load(channel.id).entries == (entry,)


def _proof_values() -> tuple[Channel, tuple[StoredMediaItem, ...]]:
    channel = Channel(ChannelId("channel-001"), 1, "Channel 001")
    media = (
        StoredMediaItem(
            MediaItem(MediaItemId("media-a"), "Programme A", timedelta(microseconds=1_320_000_001)),
            "/proof/programme-a.mkv",
        ),
        StoredMediaItem(
            MediaItem(MediaItemId("media-b"), "Programme B", timedelta(microseconds=1_500_000_002)),
            "/proof/programme-b.mkv",
        ),
    )
    return channel, media
