"""Domain value validation and UTC-normalization tests."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from nostalgiabox.domain import (
    Channel,
    ChannelId,
    ContentKind,
    InvalidChannelError,
    InvalidIdentifierError,
    InvalidMediaItemError,
    InvalidTimelineEntryError,
    MediaItem,
    MediaItemId,
    NaiveDateTimeError,
    TimelineEntry,
    TimelineEntryId,
)


def test_content_kind_initially_contains_only_programme() -> None:
    assert list(ContentKind) == [ContentKind.PROGRAMME]


@pytest.mark.parametrize("identifier_type", [MediaItemId, ChannelId, TimelineEntryId])
def test_identifiers_reject_empty_values(identifier_type: Callable[[str], object]) -> None:
    with pytest.raises(InvalidIdentifierError):
        identifier_type("  ")


@pytest.mark.parametrize("duration", [timedelta(0), timedelta(microseconds=-1)])
def test_media_item_rejects_non_positive_duration(duration: timedelta) -> None:
    with pytest.raises(InvalidMediaItemError, match="duration must be greater than zero"):
        MediaItem(id=MediaItemId("media-a"), title="Programme A", duration=duration)


def test_media_item_rejects_blank_title() -> None:
    with pytest.raises(InvalidMediaItemError, match="title must not be empty"):
        MediaItem(id=MediaItemId("media-a"), title="  ", duration=timedelta(minutes=1))


@pytest.mark.parametrize("number", [0, -1])
def test_channel_rejects_non_positive_number(number: int) -> None:
    with pytest.raises(InvalidChannelError, match="number must be greater than zero"):
        Channel(id=ChannelId("channel-001"), number=number, name="Channel 001")


def test_channel_rejects_blank_name() -> None:
    with pytest.raises(InvalidChannelError, match="name must not be empty"):
        Channel(id=ChannelId("channel-001"), number=1, name="  ")


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 8, 8, 18, 0), datetime(2026, 8, 8, 18, 30, tzinfo=UTC)),
        (datetime(2026, 8, 8, 18, 0, tzinfo=UTC), datetime(2026, 8, 8, 18, 30)),
    ],
)
def test_timeline_entry_rejects_naive_boundaries(start: datetime, end: datetime) -> None:
    with pytest.raises(NaiveDateTimeError, match="naive datetime rejected"):
        _entry(start=start, end=end)


@pytest.mark.parametrize("duration", [timedelta(0), timedelta(microseconds=-1)])
def test_timeline_entry_rejects_end_not_after_start(duration: timedelta) -> None:
    start = datetime(2026, 8, 8, 18, 0, tzinfo=UTC)

    with pytest.raises(InvalidTimelineEntryError, match="end must be after"):
        _entry(start=start, end=start + duration)


def test_non_utc_aware_boundaries_are_explicitly_normalized_to_utc() -> None:
    london = ZoneInfo("Europe/London")
    entry = _entry(
        start=datetime(2026, 7, 1, 18, 0, tzinfo=london),
        end=datetime(2026, 7, 1, 18, 30, tzinfo=london),
    )

    assert entry.start_utc == datetime(2026, 7, 1, 17, 0, tzinfo=UTC)
    assert entry.end_utc == datetime(2026, 7, 1, 17, 30, tzinfo=UTC)


def _entry(*, start: datetime, end: datetime) -> TimelineEntry:
    return TimelineEntry(
        id=TimelineEntryId("entry-a"),
        channel_id=ChannelId("channel-001"),
        media_item_id=MediaItemId("media-a"),
        content_kind=ContentKind.PROGRAMME,
        start_utc=start,
        end_utc=end,
    )
