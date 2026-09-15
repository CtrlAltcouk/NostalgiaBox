"""Probe evidence persistence against disposable SQLite state."""

from dataclasses import replace
from datetime import UTC, datetime

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from nostalgiabox.domain.catalogue import (
    FilePresenceState,
    MediaFile,
    MediaFileId,
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    ProbeState,
)
from nostalgiabox.domain.probe import ProbeFailure, ProbeFailureCode, StreamFact, TechnicalMetadata
from nostalgiabox.persistence.catalogue_repositories import (
    SqlAlchemyMediaFileRepository,
    SqlAlchemyMediaSourceRepository,
)
from nostalgiabox.persistence.models import (
    MediaFileRecord,
    ProbeAttemptRecord,
    ProbeObservationRecord,
)
from nostalgiabox.persistence.probe_uow import SqlAlchemyProbeUnitOfWork
from nostalgiabox.persistence.scan_repositories import SqlAlchemyMediaInventoryRepository

_NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


def _media_file() -> MediaFile:
    return MediaFile(
        MediaFileId("file-1"),
        MediaSourceId("source-1"),
        "Episode.mkv",
        "Episode.mkv",
        FilePresenceState.PRESENT,
        size_bytes=100,
        modified_time_ns=200,
        last_seen_generation=1,
        first_observed_utc=_NOW,
        last_observed_utc=_NOW,
    )


def _store_file(factory: sessionmaker[Session]) -> MediaFile:
    source = MediaSource(MediaSourceId("source-1"), MediaSourceKind.LOCAL)
    media_file = _media_file()
    with factory() as session:
        SqlAlchemyMediaSourceRepository(session).store(source)
        SqlAlchemyMediaFileRepository(session).store(media_file)
        session.commit()
    return media_file


def test_repository_persists_immutable_attempts_observations_and_current_pointer(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, expire_on_commit=False)
    media_file = _store_file(factory)
    metadata = TechnicalMetadata(
        1_000_000,
        ("matroska",),
        (StreamFact("video", "h264", width=1920, height=1080),),
        '["Episode.mkv",100,200]',
        "capability-1",
    )

    with SqlAlchemyProbeUnitOfWork(factory) as unit_of_work:
        unit_of_work.probes.store_metadata("observation-1", media_file.id, metadata, True, _NOW)
        unit_of_work.probes.store_attempt(
            "attempt-1",
            media_file.id,
            metadata.observation_signature,
            metadata.capability_version,
            ProbeState.COMPATIBLE_CANDIDATE,
            _NOW,
            None,
        )
        assert unit_of_work.probes.update_file_if_current(
            MediaFile(
                **{
                    **{
                        field: getattr(media_file, field)
                        for field in media_file.__dataclass_fields__
                    },
                    "probe_state": ProbeState.COMPATIBLE_CANDIDATE,
                    "probe_observation_signature": metadata.observation_signature,
                    "probe_capability_version": metadata.capability_version,
                }
            ),
            metadata.observation_signature,
            media_file.probe_state,
            media_file.probe_observation_signature,
            media_file.probe_capability_version,
        )
        unit_of_work.commit()

    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ProbeAttemptRecord)) == 1
        assert session.scalar(select(func.count()).select_from(ProbeObservationRecord)) == 1
        file_record = session.get(MediaFileRecord, media_file.id.value)
        assert file_record is not None
        assert file_record.probe_state == ProbeState.COMPATIBLE_CANDIDATE.value
        assert file_record.probe_observation_signature == metadata.observation_signature


def test_failed_refresh_keeps_prior_evidence_but_moves_current_pointer_to_failure(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, expire_on_commit=False)
    media_file = _store_file(factory)
    with SqlAlchemyProbeUnitOfWork(factory) as unit_of_work:
        unit_of_work.probes.store_attempt(
            "attempt-failed",
            media_file.id,
            '["Episode.mkv",100,200]',
            "capability-2",
            ProbeState.INSPECTION_FAILED,
            _NOW,
            ProbeFailure(ProbeFailureCode.TIMEOUT, "ffprobe exceeded its time limit"),
        )
        assert unit_of_work.probes.update_file_if_current(
            MediaFile(
                **{
                    **{
                        field: getattr(media_file, field)
                        for field in media_file.__dataclass_fields__
                    },
                    "probe_state": ProbeState.INSPECTION_FAILED,
                    "probe_observation_signature": '["Episode.mkv",100,200]',
                    "probe_capability_version": "capability-2",
                }
            ),
            '["Episode.mkv",100,200]',
            media_file.probe_state,
            media_file.probe_observation_signature,
            media_file.probe_capability_version,
        )
        unit_of_work.commit()

    with factory() as session:
        attempt = session.scalar(select(ProbeAttemptRecord))
        assert attempt is not None
        assert attempt.failure_code == ProbeFailureCode.TIMEOUT.value
        assert attempt.failure_message == "ffprobe exceeded its time limit"
        record = session.get(MediaFileRecord, media_file.id.value)
        assert record is not None
        assert record.probe_state == ProbeState.INSPECTION_FAILED.value
        assert record.probe_capability_version == "capability-2"


def test_unchanged_scan_store_preserves_probe_pointer_committed_after_its_snapshot(
    persistence_engine: Engine,
) -> None:
    factory = sessionmaker(bind=persistence_engine, expire_on_commit=False)
    media_file = _store_file(factory)
    signature = '["Episode.mkv",100,200]'

    with factory() as scan_session:
        inventory = SqlAlchemyMediaInventoryRepository(scan_session)
        stale = inventory.get_present(media_file.source_id, media_file.normalized_relative_locator)
        assert stale is not None
        with SqlAlchemyProbeUnitOfWork(factory) as probe_uow:
            assert probe_uow.probes.update_file_if_current(
                replace(
                    media_file,
                    probe_state=ProbeState.COMPATIBLE_CANDIDATE,
                    probe_observation_signature=signature,
                    probe_capability_version="capability-1",
                ),
                signature,
                media_file.probe_state,
                media_file.probe_observation_signature,
                media_file.probe_capability_version,
            )
            probe_uow.commit()
        inventory.store(replace(stale, last_seen_generation=2, last_observed_utc=_NOW))
        scan_session.commit()

    with factory() as session:
        current = session.get(MediaFileRecord, media_file.id.value)
        assert current is not None
        assert current.last_seen_generation == 2
        assert current.probe_state == ProbeState.COMPATIBLE_CANDIDATE.value
        assert current.probe_observation_signature == signature
        assert current.probe_capability_version == "capability-1"
