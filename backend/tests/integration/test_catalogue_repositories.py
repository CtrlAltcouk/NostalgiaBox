"""Catalogue repository, constraint, and legacy projection integration tests."""

from datetime import timedelta

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

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
    PreferredRenditionConflictError,
    RenditionOverlapError,
)
from nostalgiabox.domain.models import MediaItem, MediaItemId
from nostalgiabox.persistence.catalogue_repositories import (
    SqlAlchemyCatalogueItemRepository,
    SqlAlchemyLegacyPlaybackProjectionResolver,
    SqlAlchemyMediaFileRepository,
    SqlAlchemyMediaSourceRepository,
    SqlAlchemyPlayableRenditionRepository,
)
from nostalgiabox.persistence.media import StoredMediaItem
from nostalgiabox.persistence.repositories import MediaRepository


def test_catalogue_repository_does_not_commit_caller_transaction(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine)
    with factory() as session:
        SqlAlchemyCatalogueItemRepository(session).store(
            CatalogueItem(CatalogueItemId("not-committed"))
        )
        session.flush()
        session.rollback()

    with factory() as session:
        assert (
            SqlAlchemyCatalogueItemRepository(session).get_by_id(CatalogueItemId("not-committed"))
            is None
        )


def test_catalogue_repositories_round_trip_all_foundation_values(
    persistence_session: Session,
) -> None:
    item, source, media_file = _store_foundation(persistence_session)
    rendition = _rendition("rendition-1", preferred=True)
    rendition_repository = SqlAlchemyPlayableRenditionRepository(persistence_session)
    rendition_repository.store(rendition)
    persistence_session.flush()

    assert SqlAlchemyCatalogueItemRepository(persistence_session).get_by_id(item.id) == item
    assert SqlAlchemyMediaSourceRepository(persistence_session).get_by_id(source.id) == source
    assert SqlAlchemyMediaFileRepository(persistence_session).get_by_id(media_file.id) == media_file
    assert rendition_repository.get_by_id(rendition.id) == rendition
    assert rendition_repository.list_for_catalogue_item(item.id) == (rendition,)
    assert rendition_repository.get_preferred(item.id) == rendition


def test_catalogue_item_can_exist_without_a_playable_file(
    persistence_session: Session,
) -> None:
    item = CatalogueItem(CatalogueItemId("unplayable"))
    SqlAlchemyCatalogueItemRepository(persistence_session).store(item)
    persistence_session.flush()

    assert SqlAlchemyLegacyPlaybackProjectionResolver(persistence_session).resolve(item.id) is None


def test_same_id_legacy_media_projects_without_changing_phase2_storage(
    persistence_session: Session,
) -> None:
    item = CatalogueItem(CatalogueItemId("legacy-1"))
    SqlAlchemyCatalogueItemRepository(persistence_session).store(item)
    MediaRepository(persistence_session).store(
        StoredMediaItem(
            MediaItem(MediaItemId("legacy-1"), "Legacy", timedelta(minutes=42)),
            "/legacy/unchanged.mkv",
        )
    )
    persistence_session.flush()

    projection = SqlAlchemyLegacyPlaybackProjectionResolver(persistence_session).resolve(item.id)

    assert projection is not None
    assert projection.physical_path == "/legacy/unchanged.mkv"
    assert projection.segment_start == timedelta()
    assert projection.logical_playable_duration == timedelta(minutes=42)


def test_adjacent_multi_episode_renditions_share_one_file(
    persistence_session: Session,
) -> None:
    _store_foundation(persistence_session)
    SqlAlchemyCatalogueItemRepository(persistence_session).store(
        CatalogueItem(CatalogueItemId("item-2"))
    )
    repository = SqlAlchemyPlayableRenditionRepository(persistence_session)
    repository.store(_rendition("episode-1", start=0, duration=100))
    repository.store(_rendition("episode-2", item="item-2", start=100, duration=200))
    persistence_session.flush()

    assert repository.get_by_id(PlayableRenditionId("episode-2")) is not None


def test_distinct_historical_file_ids_can_share_one_source_locator(
    persistence_session: Session,
) -> None:
    _, source, first = _store_foundation(persistence_session)
    second = MediaFile(
        MediaFileId("file-2"),
        source.id,
        first.normalized_relative_locator,
        first.original_relative_locator,
    )
    repository = SqlAlchemyMediaFileRepository(persistence_session)

    repository.store(second)
    persistence_session.flush()

    assert first.id != second.id
    assert repository.get_by_id(first.id) == first
    assert repository.get_by_id(second.id) == second


def test_media_file_scanner_columns_add_only_observation_and_presence_state(
    persistence_engine: Engine,
) -> None:
    columns = {column["name"] for column in inspect(persistence_engine).get_columns("media_files")}

    assert columns == {
        "id",
        "source_id",
        "normalized_relative_locator",
        "original_relative_locator",
        "presence",
        "size_bytes",
        "modified_time_ns",
        "device_id",
        "inode_id",
        "last_seen_generation",
        "first_observed_utc_us",
        "last_observed_utc_us",
        "missing_since_utc_us",
    }
    assert not any(
        marker in column
        for column in columns
        for marker in ("probe", "codec", "fingerprint", "match", "duplicate")
    )


@pytest.mark.parametrize(
    ("identifier", "normalized_locator", "original_locator"),
    [
        (" ", "valid.mkv", "valid.mkv"),
        ("file-2", " ", "valid.mkv"),
        ("file-2", "valid.mkv", " "),
    ],
)
def test_database_rejects_blank_media_file_identity_and_locators(
    persistence_session: Session,
    identifier: str,
    normalized_locator: str,
    original_locator: str,
) -> None:
    SqlAlchemyMediaSourceRepository(persistence_session).store(
        MediaSource(MediaSourceId("source-1"), MediaSourceKind.LOCAL)
    )
    persistence_session.flush()

    with pytest.raises(IntegrityError):
        persistence_session.execute(
            text(
                "INSERT INTO media_files "
                "(id, source_id, normalized_relative_locator, original_relative_locator) "
                "VALUES (:id, 'source-1', :normalized, :original)"
            ),
            {
                "id": identifier,
                "normalized": normalized_locator,
                "original": original_locator,
            },
        )


def test_database_rejects_blank_playable_rendition_identity(
    persistence_session: Session,
) -> None:
    _store_foundation(persistence_session)

    with pytest.raises(IntegrityError):
        persistence_session.execute(
            text(
                "INSERT INTO playable_renditions "
                "(id, catalogue_item_id, media_file_id, segment_start_us, "
                "segment_duration_us, logical_playable_duration_us, is_whole_file, preferred) "
                "VALUES (' ', 'item-1', 'file-1', 0, 10, 10, 0, 0)"
            )
        )


@pytest.mark.parametrize(
    ("identifier", "item", "file_id", "start", "preferred", "error_type"),
    [
        ("overlap", "item-2", "file-1", 99, False, RenditionOverlapError),
        (
            "preferred-2",
            "item-1",
            "file-2",
            0,
            True,
            PreferredRenditionConflictError,
        ),
    ],
)
def test_repository_rejects_cross_row_domain_conflicts_before_flush(
    persistence_session: Session,
    identifier: str,
    item: str,
    file_id: str,
    start: int,
    preferred: bool,
    error_type: type[Exception],
) -> None:
    _store_foundation(persistence_session)
    SqlAlchemyCatalogueItemRepository(persistence_session).store(
        CatalogueItem(CatalogueItemId("item-2"))
    )
    SqlAlchemyMediaFileRepository(persistence_session).store(
        MediaFile(MediaFileId("file-2"), MediaSourceId("source-1"), "two.mkv", "two.mkv")
    )
    persistence_session.flush()
    repository = SqlAlchemyPlayableRenditionRepository(persistence_session)
    repository.store(_rendition("first", duration=100, preferred=True))
    persistence_session.flush()

    with pytest.raises(error_type):
        repository.store(
            _rendition(
                identifier,
                item=item,
                file=file_id,
                start=start,
                duration=200,
                preferred=preferred,
            )
        )


def test_database_enforces_one_preferred_rendition_per_catalogue_item(
    persistence_session: Session,
) -> None:
    _store_foundation(persistence_session)
    persistence_session.execute(
        text("INSERT INTO playable_renditions VALUES ('one', 'item-1', 'file-1', 0, 10, 10, 0, 1)")
    )

    with pytest.raises(IntegrityError):
        persistence_session.execute(
            text(
                "INSERT INTO playable_renditions VALUES "
                "('two', 'item-1', 'file-1', 10, 10, 10, 0, 1)"
            )
        )


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM media_sources WHERE id = 'source-1'",
        "DELETE FROM media_files WHERE id = 'file-1'",
        "DELETE FROM catalogue_items WHERE id = 'item-1'",
    ],
)
def test_database_restricts_deleting_referenced_foundation_records(
    persistence_session: Session, statement: str
) -> None:
    _store_foundation(persistence_session)
    SqlAlchemyPlayableRenditionRepository(persistence_session).store(_rendition("one"))
    persistence_session.flush()

    with pytest.raises(IntegrityError):
        persistence_session.execute(text(statement))


def _store_foundation(session: Session) -> tuple[CatalogueItem, MediaSource, MediaFile]:
    item = CatalogueItem(CatalogueItemId("item-1"))
    source = MediaSource(MediaSourceId("source-1"), MediaSourceKind.LOCAL)
    media_file = MediaFile(MediaFileId("file-1"), source.id, "episodes.mkv", "episodes.mkv")
    SqlAlchemyCatalogueItemRepository(session).store(item)
    SqlAlchemyMediaSourceRepository(session).store(source)
    session.flush()
    SqlAlchemyMediaFileRepository(session).store(media_file)
    session.flush()
    return item, source, media_file


def _rendition(
    identifier: str,
    *,
    item: str = "item-1",
    file: str = "file-1",
    start: int = 0,
    duration: int = 10,
    preferred: bool = False,
) -> PlayableRendition:
    return PlayableRendition(
        PlayableRenditionId(identifier),
        CatalogueItemId(item),
        MediaFileId(file),
        timedelta(microseconds=start),
        timedelta(microseconds=duration),
        timedelta(microseconds=duration),
        False,
        preferred,
    )
