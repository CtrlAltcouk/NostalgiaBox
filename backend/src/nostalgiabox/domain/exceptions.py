"""Explicit failures raised by the pure timeline domain."""


class TimelineDomainError(Exception):
    """Base class for timeline-domain failures."""


class InvalidIdentifierError(TimelineDomainError):
    """A stable domain identifier is empty or invalid."""


class InvalidMediaItemError(TimelineDomainError):
    """A media item violates a domain invariant."""


class InvalidChannelError(TimelineDomainError):
    """A channel violates a domain invariant."""


class NaiveDateTimeError(TimelineDomainError):
    """A datetime lacks an explicit UTC offset."""


class InvalidTimelineEntryError(TimelineDomainError):
    """A timeline entry has invalid boundaries."""


class EmptyTimelineError(TimelineDomainError):
    """A channel timeline has no entries."""


class TimelineChannelMismatchError(TimelineDomainError):
    """A timeline contains an entry for a different channel."""


class TimelineGapError(TimelineDomainError):
    """Adjacent timeline entries are separated by a gap."""


class TimelineOverlapError(TimelineDomainError):
    """Adjacent timeline entries overlap."""


class TimelineOrderError(TimelineDomainError):
    """Timeline entries are not supplied in chronological order."""


class TimelineNotCoveredError(TimelineDomainError):
    """A requested instant is outside the available timeline."""
