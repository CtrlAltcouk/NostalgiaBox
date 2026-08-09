"""SQLAlchemy adapters for the pure catalogue foundation ports."""

from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from nostalgiabox.application.catalogue import CataloguePlaybackProjection
from nostalgiabox.domain.catalogue import (
    CatalogueItem,
    CatalogueItemId,
    MediaFile,
    MediaFileId,
    MediaSource,
    MediaSourceId,
    PlayableRendition,
    PlayableRenditionId,
    validate_rendition_set,
)
from nostalgiabox.domain.models import MediaItemId
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
from nostalgiabox.persistence.models import (
    CatalogueItemRecord,
    MediaFileRecord,
    MediaSourceRecord,
    PlayableRenditionRecord,
)
from nostalgiabox.persistence.repositories import MediaRepository


class SqlAlchemyCatalogueItemRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def store(self, item: CatalogueItem) -> None:
        if self._session.get(CatalogueItemRecord, item.id.value) is None:
            self._session.add(catalogue_item_to_record(item))

    def get_by_id(self, item_id: CatalogueItemId) -> CatalogueItem | None:
        record = self._session.get(CatalogueItemRecord, item_id.value)
        return None if record is None else catalogue_item_from_record(record)


class SqlAlchemyMediaSourceRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def store(self, source: MediaSource) -> None:
        record = self._session.get(MediaSourceRecord, source.id.value)
        if record is None:
            self._session.add(media_source_to_record(source))
        else:
            record.kind = source.kind.value

    def get_by_id(self, source_id: MediaSourceId) -> MediaSource | None:
        record = self._session.get(MediaSourceRecord, source_id.value)
        return None if record is None else media_source_from_record(record)


class SqlAlchemyMediaFileRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def store(self, media_file: MediaFile) -> None:
        record = self._session.get(MediaFileRecord, media_file.id.value)
        if record is None:
            self._session.add(media_file_to_record(media_file))
        else:
            record.source_id = media_file.source_id.value
            record.normalized_relative_locator = media_file.normalized_relative_locator
            record.original_relative_locator = media_file.original_relative_locator

    def get_by_id(self, media_file_id: MediaFileId) -> MediaFile | None:
        record = self._session.get(MediaFileRecord, media_file_id.value)
        return None if record is None else media_file_from_record(record)


class SqlAlchemyPlayableRenditionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def store(self, rendition: PlayableRendition) -> None:
        records = list(
            self._session.scalars(
                select(PlayableRenditionRecord).where(
                    or_(
                        PlayableRenditionRecord.catalogue_item_id
                        == rendition.catalogue_item_id.value,
                        PlayableRenditionRecord.media_file_id == rendition.media_file_id.value,
                    )
                )
            ).all()
        )
        pending = [
            record
            for record in self._session.new
            if isinstance(record, PlayableRenditionRecord)
            and (
                record.catalogue_item_id == rendition.catalogue_item_id.value
                or record.media_file_id == rendition.media_file_id.value
            )
        ]
        records.extend(record for record in pending if record not in records)
        peers = [
            rendition_from_record(record) for record in records if record.id != rendition.id.value
        ]
        validate_rendition_set(tuple([*peers, rendition]))

        record = self._session.get(PlayableRenditionRecord, rendition.id.value)
        encoded = rendition_to_record(rendition)
        if record is None:
            self._session.add(encoded)
            return
        record.catalogue_item_id = encoded.catalogue_item_id
        record.media_file_id = encoded.media_file_id
        record.segment_start_us = encoded.segment_start_us
        record.segment_duration_us = encoded.segment_duration_us
        record.logical_playable_duration_us = encoded.logical_playable_duration_us
        record.is_whole_file = encoded.is_whole_file
        record.preferred = encoded.preferred

    def get_by_id(self, rendition_id: PlayableRenditionId) -> PlayableRendition | None:
        record = self._session.get(PlayableRenditionRecord, rendition_id.value)
        return None if record is None else rendition_from_record(record)

    def list_for_catalogue_item(self, item_id: CatalogueItemId) -> tuple[PlayableRendition, ...]:
        records = self._session.scalars(
            select(PlayableRenditionRecord)
            .where(PlayableRenditionRecord.catalogue_item_id == item_id.value)
            .order_by(PlayableRenditionRecord.id)
        ).all()
        return tuple(rendition_from_record(record) for record in records)

    def get_preferred(self, item_id: CatalogueItemId) -> PlayableRendition | None:
        record = self._session.scalar(
            select(PlayableRenditionRecord).where(
                PlayableRenditionRecord.catalogue_item_id == item_id.value,
                PlayableRenditionRecord.preferred.is_(True),
            )
        )
        return None if record is None else rendition_from_record(record)


class SqlAlchemyLegacyPlaybackProjectionResolver:
    """Project same-ID Phase 2 media rows without changing the Phase 2 runtime."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def resolve(self, item_id: CatalogueItemId) -> CataloguePlaybackProjection | None:
        if self._session.get(CatalogueItemRecord, item_id.value) is None:
            return None
        stored_media = MediaRepository(self._session).get_by_id(MediaItemId(item_id.value))
        if stored_media is None:
            return None
        return CataloguePlaybackProjection(
            catalogue_item_id=item_id,
            physical_path=stored_media.path,
            segment_start=timedelta(),
            segment_duration=stored_media.media_item.duration,
            logical_playable_duration=stored_media.media_item.duration,
        )
