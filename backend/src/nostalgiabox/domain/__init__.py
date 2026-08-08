"""Pure NostalgiaBox domain types and timeline rules."""

from nostalgiabox.domain.clock import Clock, SystemClock
from nostalgiabox.domain.exceptions import (
    EmptyTimelineError,
    InvalidChannelError,
    InvalidIdentifierError,
    InvalidMediaItemError,
    InvalidTimelineEntryError,
    NaiveDateTimeError,
    TimelineChannelMismatchError,
    TimelineGapError,
    TimelineNotCoveredError,
    TimelineOrderError,
    TimelineOverlapError,
)
from nostalgiabox.domain.models import (
    Channel,
    ChannelId,
    ContentKind,
    MediaItem,
    MediaItemId,
    TimelineEntry,
    TimelineEntryId,
)
from nostalgiabox.domain.timeline import (
    ChannelTimeline,
    ResolvedTimelineEntry,
    build_sequential_timeline,
    resolve_active_entry,
)

__all__ = [
    "Channel",
    "ChannelId",
    "ChannelTimeline",
    "Clock",
    "ContentKind",
    "EmptyTimelineError",
    "InvalidChannelError",
    "InvalidIdentifierError",
    "InvalidMediaItemError",
    "InvalidTimelineEntryError",
    "MediaItem",
    "MediaItemId",
    "NaiveDateTimeError",
    "ResolvedTimelineEntry",
    "SystemClock",
    "TimelineChannelMismatchError",
    "TimelineEntry",
    "TimelineEntryId",
    "TimelineGapError",
    "TimelineNotCoveredError",
    "TimelineOrderError",
    "TimelineOverlapError",
    "build_sequential_timeline",
    "resolve_active_entry",
]
