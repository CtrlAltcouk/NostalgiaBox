"""Exact integer codecs for domain time and duration values."""

from datetime import UTC, datetime, timedelta

from nostalgiabox.domain.time import normalize_utc

_MICROSECONDS_PER_SECOND = 1_000_000
_SECONDS_PER_DAY = 86_400
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def timedelta_to_microseconds(value: timedelta) -> int:
    """Encode a timedelta exactly without floating-point arithmetic."""
    return (
        value.days * _SECONDS_PER_DAY + value.seconds
    ) * _MICROSECONDS_PER_SECOND + value.microseconds


def microseconds_to_timedelta(value: int) -> timedelta:
    """Decode an exact signed integer microsecond duration."""
    return timedelta(microseconds=value)


def datetime_to_epoch_microseconds(value: datetime) -> int:
    """Encode an aware instant as signed UTC epoch microseconds exactly."""
    utc_value = normalize_utc(value, field_name="persisted datetime")
    return timedelta_to_microseconds(utc_value - _EPOCH)


def epoch_microseconds_to_datetime(value: int) -> datetime:
    """Decode signed UTC epoch microseconds to an aware UTC datetime."""
    return _EPOCH + microseconds_to_timedelta(value)
