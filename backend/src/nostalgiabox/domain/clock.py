"""Clock port and production UTC implementation."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Source of the current absolute time for application orchestration."""

    def now(self) -> datetime:
        """Return the current timezone-aware instant."""
        ...


class SystemClock:
    """Production clock backed by the system UTC clock."""

    def now(self) -> datetime:
        """Return the current instant in UTC."""
        return datetime.now(UTC)
