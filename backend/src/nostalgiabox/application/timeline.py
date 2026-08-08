"""Timeline application operations using injected domain ports."""

from nostalgiabox.domain.clock import Clock
from nostalgiabox.domain.timeline import (
    ChannelTimeline,
    ResolvedTimelineEntry,
    resolve_active_entry,
)


def resolve_current_entry(timeline: ChannelTimeline, clock: Clock) -> ResolvedTimelineEntry:
    """Resolve a channel timeline using an injected clock."""
    return resolve_active_entry(timeline, clock.now())
