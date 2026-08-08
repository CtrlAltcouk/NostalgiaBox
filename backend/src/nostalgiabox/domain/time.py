"""UTC normalization for domain time boundaries."""

from datetime import UTC, datetime

from nostalgiabox.domain.exceptions import NaiveDateTimeError


def normalize_utc(value: datetime, *, field_name: str) -> datetime:
    """Normalize an aware datetime to UTC without interpreting naive values."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise NaiveDateTimeError(f"{field_name} must be timezone-aware; naive datetime rejected")
    return value.astimezone(UTC)
