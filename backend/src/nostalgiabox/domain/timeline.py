"""Contiguous timeline construction, validation and active-entry resolution."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from nostalgiabox.domain.exceptions import (
    EmptyTimelineError,
    TimelineChannelMismatchError,
    TimelineGapError,
    TimelineNotCoveredError,
    TimelineOrderError,
    TimelineOverlapError,
)
from nostalgiabox.domain.models import (
    Channel,
    ContentKind,
    MediaItem,
    TimelineEntry,
    TimelineEntryId,
)
from nostalgiabox.domain.time import normalize_utc


@dataclass(frozen=True, slots=True)
class ChannelTimeline:
    """A non-empty, ordered and contiguous timeline for one channel."""

    channel: Channel
    entries: tuple[TimelineEntry, ...]

    def __post_init__(self) -> None:
        entries = tuple(self.entries)
        object.__setattr__(self, "entries", entries)
        if not entries:
            raise EmptyTimelineError(f"channel {self.channel.id.value} timeline must not be empty")

        previous: TimelineEntry | None = None
        for entry in entries:
            if entry.channel_id != self.channel.id:
                raise TimelineChannelMismatchError(
                    f"entry {entry.id.value} belongs to channel {entry.channel_id.value}, "
                    f"not {self.channel.id.value}"
                )
            if previous is not None:
                if entry.start_utc < previous.start_utc:
                    raise TimelineOrderError(
                        f"entry {entry.id.value} starts before preceding entry {previous.id.value}"
                    )
                if entry.start_utc < previous.end_utc:
                    raise TimelineOverlapError(
                        f"entry {entry.id.value} overlaps preceding entry {previous.id.value}"
                    )
                if entry.start_utc > previous.end_utc:
                    raise TimelineGapError(
                        f"gap between entries {previous.id.value} and {entry.id.value}"
                    )
            previous = entry


@dataclass(frozen=True, slots=True)
class ResolvedTimelineEntry:
    """The active entry and exact elapsed wall-clock offset within it."""

    entry: TimelineEntry
    live_offset: timedelta


def resolve_active_entry(timeline: ChannelTimeline, now: datetime) -> ResolvedTimelineEntry:
    """Resolve the unique entry satisfying ``start <= now < end``."""
    now_utc = normalize_utc(now, field_name="timeline resolution time")
    for entry in timeline.entries:
        if entry.start_utc <= now_utc < entry.end_utc:
            return ResolvedTimelineEntry(entry=entry, live_offset=now_utc - entry.start_utc)

    raise TimelineNotCoveredError(
        f"{now_utc.isoformat()} is outside channel {timeline.channel.id.value} timeline coverage "
        f"[{timeline.entries[0].start_utc.isoformat()}, "
        f"{timeline.entries[-1].end_utc.isoformat()})"
    )


def build_sequential_timeline(
    channel: Channel,
    start: datetime,
    media_items: Sequence[MediaItem],
) -> ChannelTimeline:
    """Build contiguous programme entries in supplied media order without persistence."""
    current_start = normalize_utc(start, field_name="timeline start")
    entries: list[TimelineEntry] = []

    for index, media_item in enumerate(media_items):
        current_end = current_start + media_item.duration
        entry_id = TimelineEntryId(
            f"{channel.id.value}:{current_start.isoformat(timespec='microseconds')}:{index}"
        )
        entries.append(
            TimelineEntry(
                id=entry_id,
                channel_id=channel.id,
                media_item_id=media_item.id,
                content_kind=ContentKind.PROGRAMME,
                start_utc=current_start,
                end_utc=current_end,
            )
        )
        current_start = current_end

    return ChannelTimeline(channel=channel, entries=tuple(entries))
