"""Controlled persistence-to-domain conversion failure tests."""

import pytest

from nostalgiabox.persistence.errors import (
    PersistenceConversionError,
    UnknownContentKindError,
)
from nostalgiabox.persistence.mappers import media_from_record, timeline_entry_from_record
from nostalgiabox.persistence.models import MediaItemRecord, TimelineEntryRecord


def test_invalid_persisted_duration_fails_explicitly() -> None:
    record = MediaItemRecord(id="media-a", title="Programme A", duration_us=0, path="/proof/a")

    with pytest.raises(PersistenceConversionError, match="invalid persisted values"):
        media_from_record(record)


def test_unknown_persisted_content_kind_fails_explicitly() -> None:
    record = TimelineEntryRecord(
        id="entry-a",
        channel_id="channel-001",
        media_item_id="media-a",
        content_kind="unknown",
        start_utc_us=0,
        end_utc_us=1,
    )

    with pytest.raises(UnknownContentKindError, match="unknown content kind"):
        timeline_entry_from_record(record)


def test_invalid_persisted_timeline_boundary_fails_explicitly() -> None:
    record = TimelineEntryRecord(
        id="entry-a",
        channel_id="channel-001",
        media_item_id="media-a",
        content_kind="programme",
        start_utc_us=1,
        end_utc_us=1,
    )

    with pytest.raises(PersistenceConversionError, match="invalid persisted values"):
        timeline_entry_from_record(record)
