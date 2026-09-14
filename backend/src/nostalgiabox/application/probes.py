"""Probe coordination deliberately separate from discovery and its transactions."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import replace
from datetime import datetime
from typing import Protocol, Self
from uuid import uuid4

from nostalgiabox.domain.catalogue import FilePresenceState, MediaFile, MediaFileId, ProbeState
from nostalgiabox.domain.clock import Clock
from nostalgiabox.domain.probe import (
    ProbeFailure,
    ProbeFailureCode,
    TechnicalMetadata,
    compatible,
)
from nostalgiabox.domain.scanning import encode_cheap_signature


class ProbeGateway(Protocol):
    """Technical metadata port; implementations must not expose raw probe JSON."""

    capability_version: str

    def inspect(
        self, path: str, observation_signature: str
    ) -> TechnicalMetadata | ProbeFailure: ...


class ProbeRepository(Protocol):
    """Persistence port for immutable attempt/evidence records and current state."""

    def get_file(self, media_file_id: MediaFileId) -> MediaFile | None: ...

    def store_attempt(
        self,
        attempt_id: str,
        media_file_id: MediaFileId,
        signature: str,
        capability: str,
        state: ProbeState,
        attempted_utc: datetime,
        failure: ProbeFailure | None,
    ) -> None: ...

    def store_metadata(
        self,
        observation_id: str,
        media_file_id: MediaFileId,
        metadata: TechnicalMetadata,
        candidate: bool,
        inspected_utc: datetime,
    ) -> None: ...

    def update_file(self, media_file: MediaFile) -> None: ...


class ProbeUnitOfWork(AbstractContextManager["ProbeUnitOfWork"], Protocol):
    @property
    def probes(self) -> ProbeRepository: ...

    def __enter__(self) -> Self: ...

    def commit(self) -> None: ...


ProbeUnitOfWorkFactory = Callable[[], ProbeUnitOfWork]
ProbeIdFactory = Callable[[], str]


class ProbeCoordinator:
    """Snapshot, inspect outside SQL work, then persist only if still current."""

    def __init__(
        self,
        uow_factory: ProbeUnitOfWorkFactory,
        gateway: ProbeGateway,
        clock: Clock,
        path_resolver: Callable[[MediaFile], str],
        id_factory: ProbeIdFactory | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._gateway = gateway
        self._clock = clock
        self._path_resolver = path_resolver
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def inspect(self, media_file_id: MediaFileId) -> ProbeState:
        """Inspect exactly one present discovery observation.

        The first UoW closes before resolving/running the process. The second
        rejects output when scan observation evidence changed meanwhile.
        """
        with self._uow_factory() as unit_of_work:
            media_file = unit_of_work.probes.get_file(media_file_id)
        if media_file is None or media_file.presence is not FilePresenceState.PRESENT:
            return ProbeState.DISCOVERED

        signature = observation_signature(media_file)
        capability_version = self._gateway.capability_version
        try:
            result = self._gateway.inspect(self._path_resolver(media_file), signature)
        except Exception:
            result = ProbeFailure(
                ProbeFailureCode.EXECUTION_FAILED,
                "Technical inspection could not be completed.",
            )
        if not isinstance(result, (TechnicalMetadata, ProbeFailure)):
            result = ProbeFailure(
                ProbeFailureCode.INVALID_METADATA,
                "Technical inspection returned an invalid result.",
            )
        elif isinstance(result, TechnicalMetadata) and (
            result.observation_signature != signature
            or result.capability_version != capability_version
        ):
            result = ProbeFailure(
                ProbeFailureCode.INVALID_METADATA,
                "Technical inspection returned mismatched evidence.",
            )
        attempted_at = self._clock.now()

        with self._uow_factory() as unit_of_work:
            current = unit_of_work.probes.get_file(media_file_id)
            if current is None or current.presence is not FilePresenceState.PRESENT:
                return ProbeState.DISCOVERED
            if observation_signature(current) != signature:
                return ProbeState.DISCOVERED

            if isinstance(result, ProbeFailure):
                state = ProbeState.INSPECTION_FAILED
                unit_of_work.probes.store_attempt(
                    self._id_factory(),
                    media_file_id,
                    signature,
                    self._gateway.capability_version,
                    state,
                    attempted_at,
                    result,
                )
            else:
                is_candidate = compatible(result)
                state = ProbeState.COMPATIBLE_CANDIDATE if is_candidate else ProbeState.UNSUPPORTED
                unit_of_work.probes.store_metadata(
                    self._id_factory(), media_file_id, result, is_candidate, attempted_at
                )
                unit_of_work.probes.store_attempt(
                    self._id_factory(),
                    media_file_id,
                    signature,
                    result.capability_version,
                    state,
                    attempted_at,
                    None,
                )
                capability_version = result.capability_version

            unit_of_work.probes.update_file(
                replace(
                    current,
                    probe_state=state,
                    probe_observation_signature=signature,
                    probe_capability_version=capability_version,
                )
            )
            unit_of_work.commit()
        return state


def observation_signature(media_file: MediaFile) -> str:
    """Encode precisely the Task 3.3 normalized locator/size/mtime signature."""
    if media_file.size_bytes is None or media_file.modified_time_ns is None:
        raise ValueError("a probeable file requires a Task 3.3 cheap observation")
    return encode_cheap_signature(
        (
            media_file.normalized_relative_locator,
            media_file.size_bytes,
            media_file.modified_time_ns,
        )
    )
