"""Probe coordinator isolation and refresh state tests."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import UTC, datetime

from nostalgiabox.application.probes import ProbeCoordinator, observation_signature
from nostalgiabox.domain.catalogue import (
    FilePresenceState,
    MediaFile,
    MediaFileId,
    MediaSourceId,
    ProbeState,
)
from nostalgiabox.domain.probe import ProbeFailure, ProbeFailureCode, StreamFact, TechnicalMetadata

_NOW = datetime(2026, 9, 14, 12, tzinfo=UTC)


class FakeClock:
    def now(self) -> datetime:
        return _NOW


class InMemoryRepository:
    def __init__(self, files: dict[str, MediaFile]) -> None:
        self.files = files
        self.attempts: list[tuple[object, ...]] = []
        self.metadata: list[tuple[object, ...]] = []
        self.before_cas: Callable[[], None] | None = None

    def get_file(self, media_file_id: MediaFileId) -> MediaFile | None:
        return self.files.get(media_file_id.value)

    def store_attempt(self, *args: object) -> None:
        self.attempts.append(args)

    def store_metadata(self, *args: object) -> None:
        self.metadata.append(args)

    def update_file_if_current(
        self, media_file: MediaFile, expected_observation_signature: str
    ) -> bool:
        if self.before_cas is not None:
            self.before_cas()
            self.before_cas = None
        current = self.files.get(media_file.id.value)
        if current is None or observation_signature(current) != expected_observation_signature:
            return False
        self.files[media_file.id.value] = media_file
        return True


class FakeUow(AbstractContextManager["FakeUow"]):
    def __init__(self, repository: InMemoryRepository, events: list[str]) -> None:
        self._repository = repository
        self._events = events
        self.probes = repository

    def __enter__(self) -> "FakeUow":
        self._events.append("enter")
        return self

    def __exit__(self, *args: object) -> None:
        self._events.append("exit")

    def commit(self) -> None:
        self._events.append("commit")


class FakeGateway:
    capability_version = "capability-1"

    def __init__(self, result: TechnicalMetadata | ProbeFailure, events: list[str]) -> None:
        self.result = result
        self.events = events
        self.on_inspect: Callable[[str, str], TechnicalMetadata | ProbeFailure] | None = None

    def inspect(self, path: str, observation_signature: str) -> TechnicalMetadata | ProbeFailure:
        self.events.append("inspect")
        if self.on_inspect is not None:
            return self.on_inspect(path, observation_signature)
        return self.result


def _file(**changes: object) -> MediaFile:
    values: dict[str, object] = {
        "id": MediaFileId("file-1"),
        "source_id": MediaSourceId("source-1"),
        "normalized_relative_locator": "Series/Episode.mkv",
        "original_relative_locator": "Series/Episode.mkv",
        "presence": FilePresenceState.PRESENT,
        "size_bytes": 100,
        "modified_time_ns": 200,
        "last_seen_generation": 1,
        "first_observed_utc": _NOW,
        "last_observed_utc": _NOW,
    }
    values.update(changes)
    return MediaFile(**values)  # type: ignore[arg-type]


def _metadata(signature: str) -> TechnicalMetadata:
    return TechnicalMetadata(
        1,
        ("matroska",),
        (StreamFact("video", "h264", width=10, height=10),),
        signature,
        "capability-1",
    )


def _coordinator(
    repository: InMemoryRepository, gateway: FakeGateway, events: list[str]
) -> ProbeCoordinator:
    return ProbeCoordinator(
        lambda: FakeUow(repository, events),
        gateway,
        FakeClock(),
        lambda media_file: f"/media/{media_file.normalized_relative_locator}",
        iter(("metadata-1", "attempt-1", "metadata-2", "attempt-2")).__next__,
    )


def test_success_persists_immutable_metadata_and_attempt_after_process_uow_closed() -> None:
    media_file = _file()
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    coordinator = _coordinator(
        repository, FakeGateway(_metadata(observation_signature(media_file)), events), events
    )

    state = coordinator.inspect(media_file.id)

    assert state is ProbeState.COMPATIBLE_CANDIDATE
    assert events[:3] == ["enter", "exit", "inspect"]
    assert events[-3:] == ["enter", "commit", "exit"]
    assert len(repository.metadata) == len(repository.attempts) == 1
    assert repository.files["file-1"].probe_state is ProbeState.COMPATIBLE_CANDIDATE


def test_valid_parsed_but_conservatively_rejected_media_is_unsupported() -> None:
    media_file = _file()
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    unsupported = TechnicalMetadata(
        0,
        ("mp3",),
        (StreamFact("audio", "mp3"),),
        observation_signature(media_file),
        "capability-1",
    )

    state = _coordinator(repository, FakeGateway(unsupported, events), events).inspect(
        media_file.id
    )

    assert state is ProbeState.UNSUPPORTED
    assert len(repository.metadata) == 1
    assert repository.files["file-1"].probe_state is ProbeState.UNSUPPORTED


def test_failure_replaces_current_pointer_for_same_signature_and_preserves_old_metadata() -> None:
    media_file = replace(
        _file(),
        probe_state=ProbeState.COMPATIBLE_CANDIDATE,
        probe_observation_signature=observation_signature(_file()),
        probe_capability_version="old-capability",
    )
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    failure = ProbeFailure(ProbeFailureCode.TIMEOUT, "ffprobe exceeded its time limit")

    state = _coordinator(repository, FakeGateway(failure, events), events).inspect(media_file.id)

    assert state is ProbeState.INSPECTION_FAILED
    assert not repository.metadata
    assert repository.attempts[0][-1] == failure
    current = repository.files["file-1"]
    assert current.probe_state is ProbeState.INSPECTION_FAILED
    assert current.probe_capability_version == "capability-1"


def test_changed_signature_during_probe_discards_result_without_writing_evidence() -> None:
    media_file = _file()
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    gateway = FakeGateway(_metadata(observation_signature(media_file)), events)

    def mutate_after_inspection(path: str, signature: str) -> TechnicalMetadata | ProbeFailure:
        events.append("inspect")
        repository.files["file-1"] = replace(media_file, modified_time_ns=201)
        return _metadata(signature)

    gateway.on_inspect = mutate_after_inspection
    state = _coordinator(repository, gateway, events).inspect(media_file.id)

    assert state is ProbeState.DISCOVERED
    assert not repository.attempts
    assert not repository.metadata
    assert repository.files["file-1"].probe_state is ProbeState.DISCOVERED


def test_missing_file_is_not_probed() -> None:
    media_file = _file(presence=FilePresenceState.MISSING, missing_since_utc=_NOW)
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    state = _coordinator(repository, FakeGateway(_metadata("irrelevant"), events), events).inspect(
        media_file.id
    )

    assert state is ProbeState.DISCOVERED
    assert events == ["enter", "exit"]


def test_gateway_exception_is_sanitized_and_persisted_as_inspection_failure() -> None:
    media_file = _file()
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    gateway = FakeGateway(_metadata(observation_signature(media_file)), events)

    def raise_from_gateway(path: str, signature: str) -> TechnicalMetadata | ProbeFailure:
        raise RuntimeError(f"unexpected probe path {path} for {signature}")

    gateway.on_inspect = raise_from_gateway
    state = _coordinator(repository, gateway, events).inspect(media_file.id)

    assert state is ProbeState.INSPECTION_FAILED
    failure = repository.attempts[0][-1]
    assert isinstance(failure, ProbeFailure)
    assert failure.code is ProbeFailureCode.EXECUTION_FAILED
    assert "/media" not in failure.message


def test_mismatched_metadata_is_rejected_and_does_not_become_current_facts() -> None:
    media_file = _file()
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    mismatch = TechnicalMetadata(
        1,
        ("matroska",),
        (StreamFact("video", "h264", width=10, height=10),),
        observation_signature(media_file),
        "other-capability",
    )

    state = _coordinator(repository, FakeGateway(mismatch, events), events).inspect(media_file.id)

    assert state is ProbeState.INSPECTION_FAILED
    assert not repository.metadata
    failure = repository.attempts[0][-1]
    assert isinstance(failure, ProbeFailure)
    assert failure.code is ProbeFailureCode.INVALID_METADATA


def test_unchanged_current_capability_is_not_reprobed_without_refresh() -> None:
    original = _file()
    media_file = replace(
        original,
        probe_state=ProbeState.COMPATIBLE_CANDIDATE,
        probe_observation_signature=observation_signature(original),
        probe_capability_version="capability-1",
    )
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []

    state = _coordinator(
        repository, FakeGateway(_metadata(observation_signature(original)), events), events
    ).inspect(media_file.id)

    assert state is ProbeState.COMPATIBLE_CANDIDATE
    assert events == ["enter", "exit"]
    assert not repository.attempts


def test_explicit_refresh_reprobes_unchanged_current_capability() -> None:
    original = _file()
    media_file = replace(
        original,
        probe_state=ProbeState.COMPATIBLE_CANDIDATE,
        probe_observation_signature=observation_signature(original),
        probe_capability_version="capability-1",
    )
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []

    state = _coordinator(
        repository, FakeGateway(_metadata(observation_signature(original)), events), events
    ).inspect(media_file.id, refresh=True)

    assert state is ProbeState.COMPATIBLE_CANDIDATE
    assert "inspect" in events
    assert len(repository.attempts) == 1


def test_second_uow_cas_rejects_a_signature_changed_after_the_process() -> None:
    media_file = _file()
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    repository.before_cas = lambda: repository.files.__setitem__(
        "file-1", replace(media_file, modified_time_ns=201)
    )

    state = _coordinator(
        repository, FakeGateway(_metadata(observation_signature(media_file)), events), events
    ).inspect(media_file.id)

    assert state is ProbeState.DISCOVERED
    assert not repository.attempts
    assert not repository.metadata
    assert repository.files["file-1"].modified_time_ns == 201


def test_capability_is_snapshotted_for_result_attempt_and_current_pointer() -> None:
    media_file = _file()
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    gateway = FakeGateway(_metadata(observation_signature(media_file)), events)

    def change_capability(path: str, signature: str) -> TechnicalMetadata:
        gateway.capability_version = "capability-2"
        return _metadata(signature)

    gateway.on_inspect = change_capability
    state = _coordinator(repository, gateway, events).inspect(media_file.id)

    assert state is ProbeState.COMPATIBLE_CANDIDATE
    assert repository.attempts[0][3] == "capability-1"
    assert repository.files["file-1"].probe_capability_version == "capability-1"


def test_capability_snapshot_is_retained_for_failures() -> None:
    media_file = _file()
    repository = InMemoryRepository({"file-1": media_file})
    events: list[str] = []
    gateway = FakeGateway(
        ProbeFailure(ProbeFailureCode.TIMEOUT, "ffprobe exceeded its time limit"), events
    )

    def change_capability(path: str, signature: str) -> ProbeFailure:
        gateway.capability_version = "capability-2"
        return ProbeFailure(ProbeFailureCode.TIMEOUT, "ffprobe exceeded its time limit")

    gateway.on_inspect = change_capability
    state = _coordinator(repository, gateway, events).inspect(media_file.id)

    assert state is ProbeState.INSPECTION_FAILED
    assert repository.attempts[0][3] == "capability-1"
    assert repository.files["file-1"].probe_capability_version == "capability-1"
