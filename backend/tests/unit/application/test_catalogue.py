"""Application-level catalogue playback projection tests."""

from datetime import timedelta

import pytest

from nostalgiabox.application.catalogue import CataloguePlaybackProjection
from nostalgiabox.domain.catalogue import (
    CatalogueItemId,
    MediaFileId,
    PlayableRendition,
    PlayableRenditionId,
)


def test_projection_carries_path_origin_and_exact_logical_bounds() -> None:
    rendition = PlayableRendition(
        id=PlayableRenditionId("rendition-1"),
        catalogue_item_id=CatalogueItemId("item-1"),
        media_file_id=MediaFileId("file-1"),
        segment_start=timedelta(seconds=30),
        segment_duration=timedelta(minutes=20),
        logical_playable_duration=timedelta(minutes=19, seconds=59),
        is_whole_file=False,
    )

    projection = CataloguePlaybackProjection.from_rendition(
        rendition, "/resolved/library/episodes.mkv"
    )

    assert projection.physical_path == "/resolved/library/episodes.mkv"
    assert projection.segment_start == timedelta(seconds=30)
    assert projection.segment_end == timedelta(minutes=20, seconds=30)
    assert projection.physical_position(timedelta(seconds=5)) == timedelta(seconds=35)


@pytest.mark.parametrize("offset", [timedelta(microseconds=-1), timedelta(minutes=20)])
def test_projection_rejects_offsets_outside_logical_playable_duration(
    offset: timedelta,
) -> None:
    projection = CataloguePlaybackProjection(
        catalogue_item_id=CatalogueItemId("item-1"),
        physical_path="/resolved/item.mkv",
        segment_start=timedelta(),
        segment_duration=timedelta(minutes=20),
        logical_playable_duration=timedelta(minutes=20),
    )

    with pytest.raises(ValueError, match="outside"):
        projection.physical_position(offset)
