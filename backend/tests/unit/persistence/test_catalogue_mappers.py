"""Exact catalogue ORM conversion tests."""

from datetime import timedelta

from nostalgiabox.domain.catalogue import (
    CatalogueItem,
    CatalogueItemId,
    MediaFile,
    MediaFileId,
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    PlayableRendition,
    PlayableRenditionId,
)
from nostalgiabox.persistence.catalogue_mappers import (
    catalogue_item_from_record,
    catalogue_item_to_record,
    media_file_from_record,
    media_file_to_record,
    media_source_from_record,
    media_source_to_record,
    rendition_from_record,
    rendition_to_record,
)


def test_catalogue_foundation_values_round_trip_without_precision_loss() -> None:
    item = CatalogueItem(CatalogueItemId("item-1"))
    source = MediaSource(MediaSourceId("source-1"), MediaSourceKind.SMB)
    media_file = MediaFile(
        MediaFileId("file-1"),
        source.id,
        "Series/Episode.mkv",
        "Series\\Episode.mkv",
    )
    rendition = PlayableRendition(
        PlayableRenditionId("rendition-1"),
        item.id,
        media_file.id,
        timedelta(seconds=12, microseconds=345_678),
        timedelta(seconds=50, microseconds=123_456),
        timedelta(seconds=49, microseconds=999_999),
        False,
        True,
    )

    assert catalogue_item_from_record(catalogue_item_to_record(item)) == item
    assert media_source_from_record(media_source_to_record(source)) == source
    assert media_file_from_record(media_file_to_record(media_file)) == media_file
    assert rendition_from_record(rendition_to_record(rendition)) == rendition
