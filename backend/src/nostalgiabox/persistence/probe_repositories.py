"""SQLAlchemy persistence adapter for immutable probe evidence."""

import json
from datetime import datetime

from sqlalchemy.orm import Session

from nostalgiabox.domain.catalogue import MediaFile, MediaFileId, ProbeState
from nostalgiabox.domain.probe import ProbeFailure, StreamFact, TechnicalMetadata
from nostalgiabox.persistence.catalogue_mappers import media_file_from_record, media_file_to_record
from nostalgiabox.persistence.codecs import datetime_to_epoch_microseconds
from nostalgiabox.persistence.models import (
    MediaFileRecord,
    ProbeAttemptRecord,
    ProbeObservationRecord,
)


class SqlAlchemyProbeRepository:
    """Append evidence records and update only the file's current probe pointer."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_file(self, media_file_id: MediaFileId) -> MediaFile | None:
        record = self._session.get(MediaFileRecord, media_file_id.value)
        return None if record is None else media_file_from_record(record)

    def update_file(self, media_file: MediaFile) -> None:
        record = self._session.get(MediaFileRecord, media_file.id.value)
        if record is None:
            raise RuntimeError(f"media file {media_file.id.value!r} does not exist")
        encoded = media_file_to_record(media_file)
        for field in (
            "probe_state",
            "probe_observation_signature",
            "probe_capability_version",
        ):
            setattr(record, field, getattr(encoded, field))

    def store_attempt(
        self,
        attempt_id: str,
        media_file_id: MediaFileId,
        signature: str,
        capability: str,
        state: ProbeState,
        attempted_utc: datetime,
        failure: ProbeFailure | None,
    ) -> None:
        self._session.add(
            ProbeAttemptRecord(
                id=attempt_id,
                media_file_id=media_file_id.value,
                observation_signature=signature,
                capability_version=capability,
                state=state.value,
                attempted_utc_us=datetime_to_epoch_microseconds(attempted_utc),
                failure_code=None if failure is None else failure.code.value,
                failure_message=None if failure is None else failure.message,
            )
        )

    def store_metadata(
        self,
        observation_id: str,
        media_file_id: MediaFileId,
        metadata: TechnicalMetadata,
        candidate: bool,
        inspected_utc: datetime,
    ) -> None:
        self._session.add(
            ProbeObservationRecord(
                id=observation_id,
                media_file_id=media_file_id.value,
                observation_signature=metadata.observation_signature,
                capability_version=metadata.capability_version,
                duration_us=metadata.duration_us,
                containers_json=json.dumps(metadata.containers, separators=(",", ":")),
                streams_json=json.dumps(
                    [_stream_payload(stream) for stream in metadata.streams],
                    separators=(",", ":"),
                ),
                compatible_candidate=candidate,
                inspected_utc_us=datetime_to_epoch_microseconds(inspected_utc),
            )
        )


def _stream_payload(stream: StreamFact) -> dict[str, object]:
    return {
        "codec_type": stream.codec_type,
        "codec_name": stream.codec_name,
        "language": stream.language,
        "disposition": stream.disposition,
        "width": stream.width,
        "height": stream.height,
        "frame_rate_numerator": stream.frame_rate_numerator,
        "frame_rate_denominator": stream.frame_rate_denominator,
    }
