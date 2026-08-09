"""Explicit conversion boundary for catalogue foundation records."""

from nostalgiabox.domain.catalogue import (
    CatalogueDomainError,
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
from nostalgiabox.domain.exceptions import TimelineDomainError
from nostalgiabox.persistence.codecs import microseconds_to_timedelta, timedelta_to_microseconds
from nostalgiabox.persistence.errors import PersistenceConversionError
from nostalgiabox.persistence.models import (
    CatalogueItemRecord,
    MediaFileRecord,
    MediaSourceRecord,
    PlayableRenditionRecord,
)


def catalogue_item_to_record(item: CatalogueItem) -> CatalogueItemRecord:
    return CatalogueItemRecord(id=item.id.value)


def catalogue_item_from_record(record: CatalogueItemRecord) -> CatalogueItem:
    try:
        return CatalogueItem(id=CatalogueItemId(record.id))
    except (CatalogueDomainError, TimelineDomainError) as error:
        raise PersistenceConversionError(f"catalogue item {record.id!r} is invalid") from error


def media_source_to_record(source: MediaSource) -> MediaSourceRecord:
    return MediaSourceRecord(id=source.id.value, kind=source.kind.value)


def media_source_from_record(record: MediaSourceRecord) -> MediaSource:
    try:
        return MediaSource(id=MediaSourceId(record.id), kind=MediaSourceKind(record.kind))
    except (CatalogueDomainError, TimelineDomainError, ValueError) as error:
        raise PersistenceConversionError(f"media source {record.id!r} is invalid") from error


def media_file_to_record(media_file: MediaFile) -> MediaFileRecord:
    return MediaFileRecord(
        id=media_file.id.value,
        source_id=media_file.source_id.value,
        normalized_relative_locator=media_file.normalized_relative_locator,
        original_relative_locator=media_file.original_relative_locator,
    )


def media_file_from_record(record: MediaFileRecord) -> MediaFile:
    try:
        return MediaFile(
            id=MediaFileId(record.id),
            source_id=MediaSourceId(record.source_id),
            normalized_relative_locator=record.normalized_relative_locator,
            original_relative_locator=record.original_relative_locator,
        )
    except (CatalogueDomainError, TimelineDomainError) as error:
        raise PersistenceConversionError(f"media file {record.id!r} is invalid") from error


def rendition_to_record(rendition: PlayableRendition) -> PlayableRenditionRecord:
    return PlayableRenditionRecord(
        id=rendition.id.value,
        catalogue_item_id=rendition.catalogue_item_id.value,
        media_file_id=rendition.media_file_id.value,
        segment_start_us=timedelta_to_microseconds(rendition.segment_start),
        segment_duration_us=timedelta_to_microseconds(rendition.segment_duration),
        logical_playable_duration_us=timedelta_to_microseconds(rendition.logical_playable_duration),
        is_whole_file=rendition.is_whole_file,
        preferred=rendition.preferred,
    )


def rendition_from_record(record: PlayableRenditionRecord) -> PlayableRendition:
    try:
        return PlayableRendition(
            id=PlayableRenditionId(record.id),
            catalogue_item_id=CatalogueItemId(record.catalogue_item_id),
            media_file_id=MediaFileId(record.media_file_id),
            segment_start=microseconds_to_timedelta(record.segment_start_us),
            segment_duration=microseconds_to_timedelta(record.segment_duration_us),
            logical_playable_duration=microseconds_to_timedelta(
                record.logical_playable_duration_us
            ),
            is_whole_file=record.is_whole_file,
            preferred=record.preferred,
        )
    except (CatalogueDomainError, TimelineDomainError) as error:
        raise PersistenceConversionError(f"rendition {record.id!r} is invalid") from error
