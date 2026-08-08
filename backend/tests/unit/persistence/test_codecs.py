"""Exact integer persistence codec tests."""

from datetime import UTC, datetime, timedelta

import pytest

from nostalgiabox.domain import NaiveDateTimeError
from nostalgiabox.persistence.codecs import (
    datetime_to_epoch_microseconds,
    epoch_microseconds_to_datetime,
    microseconds_to_timedelta,
    timedelta_to_microseconds,
)


@pytest.mark.parametrize(
    ("instant", "encoded"),
    [
        (datetime(1970, 1, 1, tzinfo=UTC), 0),
        (datetime(1969, 12, 31, 23, 59, 59, 999999, tzinfo=UTC), -1),
        (datetime(2026, 8, 8, 18, 0, tzinfo=UTC), 1_786_212_000_000_000),
        (datetime(2026, 8, 8, 18, 0, 0, 123456, tzinfo=UTC), 1_786_212_000_123_456),
    ],
)
def test_datetime_epoch_microseconds_round_trip_exactly(
    instant: datetime,
    encoded: int,
) -> None:
    assert datetime_to_epoch_microseconds(instant) == encoded
    reconstructed = epoch_microseconds_to_datetime(encoded)
    assert reconstructed == instant
    assert reconstructed.tzinfo is UTC


def test_datetime_codec_rejects_naive_value() -> None:
    with pytest.raises(NaiveDateTimeError):
        datetime_to_epoch_microseconds(datetime(2026, 8, 8, 18, 0))


@pytest.mark.parametrize(
    "duration",
    [
        timedelta(seconds=1),
        timedelta(microseconds=1),
        timedelta(days=2, seconds=3, microseconds=456789),
        timedelta(microseconds=-1),
    ],
)
def test_timedelta_microseconds_round_trip_exactly(duration: timedelta) -> None:
    encoded = timedelta_to_microseconds(duration)

    assert microseconds_to_timedelta(encoded) == duration
