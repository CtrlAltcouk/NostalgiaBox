"""Deterministic timeline construction, validation and resolution tests."""

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

import pytest

from nostalgiabox.application.timeline import resolve_current_entry
from nostalgiabox.domain import (
    Channel,
    ChannelId,
    ChannelTimeline,
    ContentKind,
    EmptyTimelineError,
    MediaItem,
    MediaItemId,
    NaiveDateTimeError,
    SystemClock,
    TimelineChannelMismatchError,
    TimelineEntry,
    TimelineEntryId,
    TimelineGapError,
    TimelineNotCoveredError,
    TimelineOrderError,
    TimelineOverlapError,
    build_sequential_timeline,
    resolve_active_entry,
)

from ...support.clock import FakeClock

START = datetime(2026, 8, 8, 18, 0, tzinfo=UTC)
CHANNEL = Channel(id=ChannelId("channel-001"), number=1, name="Channel 001")
MEDIA_ITEMS = (
    MediaItem(id=MediaItemId("media-a"), title="Programme A", duration=timedelta(minutes=22)),
    MediaItem(id=MediaItemId("media-b"), title="Programme B", duration=timedelta(minutes=25)),
    MediaItem(id=MediaItemId("media-c"), title="Programme C", duration=timedelta(minutes=20)),
)


def test_exact_start_resolves_with_zero_offset() -> None:
    timeline = _timeline()

    result = resolve_active_entry(timeline, timeline.entries[0].start_utc)

    assert result.entry == timeline.entries[0]
    assert result.live_offset == timedelta(0)


def test_mid_programme_resolves_with_exact_elapsed_offset() -> None:
    timeline = _timeline()

    result = resolve_active_entry(timeline, START + timedelta(minutes=31, seconds=17))

    assert result.entry == timeline.entries[1]
    assert result.live_offset == timedelta(minutes=9, seconds=17)


def test_one_microsecond_before_boundary_remains_in_current_entry() -> None:
    timeline = _timeline()
    instant = timeline.entries[0].end_utc - timedelta(microseconds=1)

    result = resolve_active_entry(timeline, instant)

    assert result.entry == timeline.entries[0]
    assert result.live_offset == timeline.entries[0].duration - timedelta(microseconds=1)


def test_exact_boundary_resolves_next_entry_with_zero_offset() -> None:
    timeline = _timeline()

    result = resolve_active_entry(timeline, timeline.entries[0].end_utc)

    assert result.entry == timeline.entries[1]
    assert result.live_offset == timedelta(0)


@pytest.mark.parametrize(
    "instant",
    [START - timedelta(microseconds=1), START + timedelta(minutes=67)],
)
def test_time_outside_timeline_raises_explicit_error(instant: datetime) -> None:
    with pytest.raises(TimelineNotCoveredError, match="outside channel"):
        resolve_active_entry(_timeline(), instant)


def test_resolution_rejects_naive_datetime() -> None:
    with pytest.raises(NaiveDateTimeError, match="timeline resolution time"):
        resolve_active_entry(_timeline(), datetime(2026, 8, 8, 18, 0))


def test_resolution_normalizes_non_utc_aware_datetime() -> None:
    london = ZoneInfo("Europe/London")
    timeline = build_sequential_timeline(
        CHANNEL,
        datetime(2026, 7, 1, 17, 0, tzinfo=UTC),
        MEDIA_ITEMS,
    )

    result = resolve_active_entry(timeline, datetime(2026, 7, 1, 18, 10, tzinfo=london))

    assert result.entry == timeline.entries[0]
    assert result.live_offset == timedelta(minutes=10)


def test_gap_is_rejected() -> None:
    first = _entry("a", START, START + timedelta(minutes=30))
    second = _entry("b", START + timedelta(minutes=31), START + timedelta(minutes=60))

    with pytest.raises(TimelineGapError):
        ChannelTimeline(CHANNEL, (first, second))


def test_overlap_is_rejected() -> None:
    first = _entry("a", START, START + timedelta(minutes=30))
    second = _entry("b", START + timedelta(minutes=29), START + timedelta(minutes=60))

    with pytest.raises(TimelineOverlapError):
        ChannelTimeline(CHANNEL, (first, second))


def test_invalid_order_is_rejected_without_reordering() -> None:
    later = _entry("later", START + timedelta(minutes=30), START + timedelta(minutes=60))
    earlier = _entry("earlier", START, START + timedelta(minutes=30))

    with pytest.raises(TimelineOrderError):
        ChannelTimeline(CHANNEL, (later, earlier))


def test_entry_for_another_channel_is_rejected() -> None:
    wrong_channel_entry = TimelineEntry(
        id=TimelineEntryId("wrong-channel-entry"),
        channel_id=ChannelId("channel-002"),
        media_item_id=MEDIA_ITEMS[0].id,
        content_kind=ContentKind.PROGRAMME,
        start_utc=START,
        end_utc=START + timedelta(minutes=22),
    )

    with pytest.raises(TimelineChannelMismatchError):
        ChannelTimeline(CHANNEL, (wrong_channel_entry,))


def test_empty_sequential_timeline_is_rejected() -> None:
    with pytest.raises(EmptyTimelineError):
        build_sequential_timeline(CHANNEL, START, ())


def test_sequential_construction_uses_supplied_order_and_exact_durations() -> None:
    timeline = _timeline()

    assert [entry.media_item_id for entry in timeline.entries] == [item.id for item in MEDIA_ITEMS]
    assert [(entry.start_utc, entry.end_utc) for entry in timeline.entries] == [
        (START, START + timedelta(minutes=22)),
        (START + timedelta(minutes=22), START + timedelta(minutes=47)),
        (START + timedelta(minutes=47), START + timedelta(minutes=67)),
    ]
    assert all(
        current.end_utc == following.start_utc for current, following in pairwise(timeline.entries)
    )


def test_sequential_construction_is_deterministic() -> None:
    assert _timeline() == _timeline()


def test_fake_clock_repeats_and_advances_across_boundary() -> None:
    timeline = _timeline()
    clock = FakeClock(START + timedelta(minutes=21))

    first_result = resolve_current_entry(timeline, clock)
    repeated_result = resolve_current_entry(timeline, clock)
    clock.advance(timedelta(minutes=1))
    boundary_result = resolve_current_entry(timeline, clock)

    assert first_result == repeated_result
    assert first_result.entry == timeline.entries[0]
    assert boundary_result.entry == timeline.entries[1]
    assert boundary_result.live_offset == timedelta(0)


def test_system_clock_returns_utc_aware_time() -> None:
    now = SystemClock().now()

    assert now.tzinfo is UTC
    assert now.utcoffset() == timedelta(0)


def test_spring_dst_transition_resolves_absolute_utc_without_ambiguity() -> None:
    london = ZoneInfo("Europe/London")
    timeline = _dst_timeline(datetime(2026, 3, 29, 0, 0, tzinfo=UTC))

    before_skip = resolve_active_entry(timeline, datetime(2026, 3, 29, 0, 30, tzinfo=london))
    after_skip = resolve_active_entry(timeline, datetime(2026, 3, 29, 2, 30, tzinfo=london))

    assert before_skip.entry == timeline.entries[0]
    assert after_skip.entry == timeline.entries[1]
    assert before_skip.live_offset == after_skip.live_offset == timedelta(minutes=30)


def test_autumn_dst_repeated_local_time_maps_to_distinct_utc_entries() -> None:
    london = ZoneInfo("Europe/London")
    timeline = _dst_timeline(datetime(2026, 10, 25, 0, 0, tzinfo=UTC))

    first_fold = resolve_active_entry(
        timeline,
        datetime(2026, 10, 25, 1, 30, tzinfo=london, fold=0),
    )
    second_fold = resolve_active_entry(
        timeline,
        datetime(2026, 10, 25, 1, 30, tzinfo=london, fold=1),
    )

    assert first_fold.entry == timeline.entries[0]
    assert second_fold.entry == timeline.entries[1]
    assert first_fold.live_offset == second_fold.live_offset == timedelta(minutes=30)


def _timeline() -> ChannelTimeline:
    return build_sequential_timeline(CHANNEL, START, MEDIA_ITEMS)


def _dst_timeline(start: datetime) -> ChannelTimeline:
    items = (
        MediaItem(MediaItemId("dst-a"), "DST A", timedelta(hours=1)),
        MediaItem(MediaItemId("dst-b"), "DST B", timedelta(hours=1)),
    )
    return build_sequential_timeline(CHANNEL, start, items)


def _entry(identifier: str, start: datetime, end: datetime) -> TimelineEntry:
    return TimelineEntry(
        id=TimelineEntryId(identifier),
        channel_id=CHANNEL.id,
        media_item_id=MediaItemId(f"media-{identifier}"),
        content_kind=ContentKind.PROGRAMME,
        start_utc=start,
        end_utc=end,
    )
