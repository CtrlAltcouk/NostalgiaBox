"""Source persistence, optimistic revision and unit-of-work integration tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nostalgiabox.application.sources import LocalSourceService, SourceAvailabilityResult
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
    SourceAvailability,
)
from nostalgiabox.persistence.catalogue_repositories import (
    SqlAlchemyCatalogueItemRepository,
    SqlAlchemyMediaFileRepository,
    SqlAlchemyMediaSourceRepository,
    SqlAlchemyPlayableRenditionRepository,
)
from nostalgiabox.persistence.database import create_session_factory
from nostalgiabox.persistence.source_uow import SqlAlchemySourceUnitOfWork
from nostalgiabox.source.local import LocalFilesystemSourceGateway
from tests.support.clock import FakeClock


def test_source_repository_round_trips_lifecycle_availability_and_timestamps(
    persistence_session: Session,
) -> None:
    source = _configured_source()
    repository = SqlAlchemyMediaSourceRepository(persistence_session)

    repository.add(source)
    persistence_session.flush()

    assert repository.get_by_id(source.id) == source
    assert repository.list() == (source,)
    assert repository.has_media_files(source.id) is False


def test_repository_revision_update_is_atomic_and_detects_stale_write(
    persistence_session: Session,
) -> None:
    source = _configured_source()
    repository = SqlAlchemyMediaSourceRepository(persistence_session)
    repository.add(source)
    persistence_session.flush()
    updated = replace(source, display_name="Renamed", revision=2)

    assert repository.update(updated, expected_revision=1) is True
    assert repository.update(source, expected_revision=1) is False
    assert repository.get_by_id(source.id) == updated


def test_repository_detects_media_file_reference_without_exposing_orm(
    persistence_session: Session,
) -> None:
    source = _configured_source()
    repository = SqlAlchemyMediaSourceRepository(persistence_session)
    repository.add(source)
    persistence_session.flush()
    SqlAlchemyMediaFileRepository(persistence_session).store(
        MediaFile(MediaFileId("file-1"), source.id, "video.mkv", "video.mkv")
    )
    persistence_session.flush()

    assert repository.has_media_files(source.id) is True


def test_sqlalchemy_unit_of_work_commits_source_service_changes(
    persistence_engine: Engine,
) -> None:
    factory = create_session_factory(persistence_engine)
    service = LocalSourceService(
        lambda: SqlAlchemySourceUnitOfWork(factory),
        _AvailableGateway(),
        FakeClock(datetime(2026, 8, 10, 12, tzinfo=UTC)),
        lambda: MediaSourceId("created"),
    )

    created = service.create_local_source("Created", "/approved/created", enabled=True)
    checked = service.check_availability(created.id)

    with factory() as session:
        stored = SqlAlchemyMediaSourceRepository(session).get_by_id(created.id)
    assert stored == checked
    assert checked.availability is SourceAvailability.AVAILABLE


def test_real_local_gateway_create_check_disable_enable_and_missing_root(
    persistence_engine: Engine,
    tmp_path: Path,
) -> None:
    approved = tmp_path / "approved"
    source_root = approved / "source"
    source_root.mkdir(parents=True)
    factory = create_session_factory(persistence_engine)
    service = LocalSourceService(
        lambda: SqlAlchemySourceUnitOfWork(factory),
        LocalFilesystemSourceGateway([str(approved)]),
        FakeClock(datetime(2026, 8, 10, 12, tzinfo=UTC)),
        lambda: MediaSourceId("real-local"),
    )

    created = service.create_local_source("Real local", str(source_root), enabled=True)
    available = service.check_availability(created.id)
    disabled = service.disable_source(created.id, available.revision)
    enabled = service.enable_source(created.id, disabled.revision)
    source_root.rmdir()
    missing = service.check_availability(enabled.id)

    assert available.availability is SourceAvailability.AVAILABLE
    assert disabled.enabled is False
    assert enabled.enabled is True
    assert missing.availability is SourceAvailability.INVALID_ROOT
    assert missing.enabled is True
    with factory() as session:
        for table in ("media_files", "catalogue_items", "timeline_entries"):
            assert session.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def test_retirement_preserves_media_file_and_catalogue_rows(
    persistence_engine: Engine,
) -> None:
    factory = create_session_factory(persistence_engine)
    source = _configured_source()
    with factory.begin() as session:
        SqlAlchemyMediaSourceRepository(session).add(source)
        session.flush()
        SqlAlchemyCatalogueItemRepository(session).store(
            CatalogueItem(CatalogueItemId("catalogue-1"))
        )
        SqlAlchemyMediaFileRepository(session).store(
            MediaFile(MediaFileId("file-1"), source.id, "video.mkv", "video.mkv")
        )
        session.flush()
        SqlAlchemyPlayableRenditionRepository(session).store(
            PlayableRendition(
                PlayableRenditionId("rendition-1"),
                CatalogueItemId("catalogue-1"),
                MediaFileId("file-1"),
                timedelta(),
                timedelta(minutes=1),
                timedelta(minutes=1),
                True,
                True,
            )
        )
        session.execute(
            text(
                "INSERT INTO media_items VALUES ('legacy-media', 'Legacy', 60000000, '/legacy.mkv')"
            )
        )
        session.execute(text("INSERT INTO channels VALUES ('channel-1', 1, 'Channel 001')"))
        session.execute(
            text(
                "INSERT INTO timeline_entries VALUES "
                "('entry-1', 'channel-1', 'legacy-media', 'programme', 0, 60000000)"
            )
        )

    service = LocalSourceService(
        lambda: SqlAlchemySourceUnitOfWork(factory),
        _AvailableGateway(),
        FakeClock(datetime(2026, 8, 10, 12, tzinfo=UTC)),
        lambda: MediaSourceId("unused"),
    )
    retired = service.retire_source(source.id, source.revision)

    with factory() as session:
        for table in (
            "media_sources",
            "media_files",
            "catalogue_items",
            "playable_renditions",
            "timeline_entries",
        ):
            assert session.scalar(text(f"SELECT count(*) FROM {table}")) == 1
    assert retired.enabled is False
    assert retired.retired_utc == datetime(2026, 8, 10, 12, tzinfo=UTC)


def test_database_rejects_invalid_source_lifecycle_state(
    persistence_session: Session,
) -> None:
    source = _configured_source()
    SqlAlchemyMediaSourceRepository(persistence_session).add(source)
    persistence_session.flush()

    invalid_statements = (
        "UPDATE media_sources SET display_name = ' ' WHERE id = 'source-1'",
        "UPDATE media_sources SET availability = 'invented' WHERE id = 'source-1'",
        "UPDATE media_sources SET revision = 0 WHERE id = 'source-1'",
        "UPDATE media_sources SET current_error_message = NULL WHERE id = 'source-1'",
    )
    for statement in invalid_statements:
        nested = persistence_session.begin_nested()
        try:
            with pytest.raises(IntegrityError):
                persistence_session.execute(text(statement))
        finally:
            nested.rollback()


class _AvailableGateway:
    def validate_root(self, configured_root: str) -> str:
        return configured_root

    def check(self, configured_root: str) -> SourceAvailabilityResult:
        return SourceAvailabilityResult(SourceAvailability.AVAILABLE)


def _configured_source() -> MediaSource:
    return MediaSource(
        MediaSourceId("source-1"),
        MediaSourceKind.LOCAL,
        display_name="Source one",
        configured_root="/approved/source-one",
        enabled=True,
        availability=SourceAvailability.UNAVAILABLE,
        last_checked_utc=datetime(2026, 8, 10, 11, 0, 0, 123456, tzinfo=UTC),
        last_successful_scan_utc=None,
        current_error_code="source.unavailable",
        current_error_message="The source is unavailable.",
        revision=1,
    )
