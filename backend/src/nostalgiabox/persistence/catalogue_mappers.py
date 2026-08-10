"""Explicit conversion boundary for catalogue foundation records."""

from datetime import datetime

from nostalgiabox.domain.catalogue import (
    CatalogueDomainError,
    CatalogueItem,
    CatalogueItemId,
    FilePresenceState,
    MediaFile,
    MediaFileId,
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    PlayableRendition,
    PlayableRenditionId,
    SourceAvailability,
)
from nostalgiabox.domain.exceptions import TimelineDomainError
from nostalgiabox.persistence.codecs import (
    datetime_to_epoch_microseconds,
    epoch_microseconds_to_datetime,
    microseconds_to_timedelta,
    timedelta_to_microseconds,
)
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
    return MediaSourceRecord(
        id=source.id.value,
        kind=source.kind.value,
        display_name=source.display_name,
        configured_root=source.configured_root,
        enabled=source.enabled,
        availability=source.availability.value,
        last_checked_utc_us=_optional_datetime_to_microseconds(source.last_checked_utc),
        last_successful_scan_utc_us=_optional_datetime_to_microseconds(
            source.last_successful_scan_utc
        ),
        current_error_code=source.current_error_code,
        current_error_message=source.current_error_message,
        retired_utc_us=_optional_datetime_to_microseconds(source.retired_utc),
        revision=source.revision,
    )


def media_source_from_record(record: MediaSourceRecord) -> MediaSource:
    try:
        return MediaSource(
            id=MediaSourceId(record.id),
            kind=MediaSourceKind(record.kind),
            display_name=record.display_name,
            configured_root=record.configured_root,
            enabled=record.enabled,
            availability=SourceAvailability(record.availability),
            last_checked_utc=_optional_microseconds_to_datetime(record.last_checked_utc_us),
            last_successful_scan_utc=_optional_microseconds_to_datetime(
                record.last_successful_scan_utc_us
            ),
            current_error_code=record.current_error_code,
            current_error_message=record.current_error_message,
            retired_utc=_optional_microseconds_to_datetime(record.retired_utc_us),
            revision=record.revision,
        )
    except (CatalogueDomainError, TimelineDomainError, ValueError, OverflowError) as error:
        raise PersistenceConversionError(f"media source {record.id!r} is invalid") from error


def _optional_datetime_to_microseconds(value: datetime | None) -> int | None:
    if value is None:
        return None
    return datetime_to_epoch_microseconds(value)


def _optional_microseconds_to_datetime(value: int | None) -> datetime | None:
    return None if value is None else epoch_microseconds_to_datetime(value)


def media_file_to_record(media_file: MediaFile) -> MediaFileRecord:
    return MediaFileRecord(
        id=media_file.id.value,
        source_id=media_file.source_id.value,
        normalized_relative_locator=media_file.normalized_relative_locator,
        original_relative_locator=media_file.original_relative_locator,
        presence=media_file.presence.value,
        size_bytes=media_file.size_bytes,
        modified_time_ns=media_file.modified_time_ns,
        device_id=media_file.device_id,
        inode_id=media_file.inode_id,
        last_seen_generation=media_file.last_seen_generation,
        first_observed_utc_us=_optional_datetime_to_microseconds(media_file.first_observed_utc),
        last_observed_utc_us=_optional_datetime_to_microseconds(media_file.last_observed_utc),
        missing_since_utc_us=_optional_datetime_to_microseconds(media_file.missing_since_utc),
    )


def media_file_from_record(record: MediaFileRecord) -> MediaFile:
    try:
        return MediaFile(
            id=MediaFileId(record.id),
            source_id=MediaSourceId(record.source_id),
            normalized_relative_locator=record.normalized_relative_locator,
            original_relative_locator=record.original_relative_locator,
            presence=FilePresenceState(record.presence),
            size_bytes=record.size_bytes,
            modified_time_ns=record.modified_time_ns,
            device_id=record.device_id,
            inode_id=record.inode_id,
            last_seen_generation=record.last_seen_generation,
            first_observed_utc=_optional_microseconds_to_datetime(record.first_observed_utc_us),
            last_observed_utc=_optional_microseconds_to_datetime(record.last_observed_utc_us),
            missing_since_utc=_optional_microseconds_to_datetime(record.missing_since_utc_us),
        )
    except (CatalogueDomainError, TimelineDomainError, ValueError, OverflowError) as error:
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
