"""Deterministic test doubles for domain ports."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from nostalgiabox.domain.time import normalize_utc


@dataclass(slots=True)
class FakeClock:
    """Mutable test clock with explicit fixed, set and advance operations."""

    current: datetime

    def __post_init__(self) -> None:
        self.current = normalize_utc(self.current, field_name="fake clock time")

    def now(self) -> datetime:
        """Return the fixed current instant."""
        return self.current

    def set(self, value: datetime) -> None:
        """Set the clock to an explicit aware instant."""
        self.current = normalize_utc(value, field_name="fake clock time")

    def advance(self, amount: timedelta) -> None:
        """Advance the clock by a non-negative exact duration."""
        if amount < timedelta(0):
            raise ValueError("fake clock cannot advance by a negative duration")
        self.current += amount
