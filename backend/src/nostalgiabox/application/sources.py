"""Local media-source lifecycle use cases and infrastructure-free ports."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass, replace
from typing import Protocol, Self

from nostalgiabox.domain.catalogue import (
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    SourceAvailability,
)
from nostalgiabox.domain.clock import Clock
from nostalgiabox.domain.time import normalize_utc


class SourceApplicationError(Exception):
    """Base class for controlled source-lifecycle failures."""


class SourceNotFoundError(SourceApplicationError):
    """A requested source identity does not exist."""


class SourceAlreadyExistsError(SourceApplicationError):
    """A create operation reused an existing stable source identity."""


class SourceAlreadyRetiredError(SourceApplicationError):
    """A terminally retired source was used by a mutable operation."""


class SourceRevisionConflictError(SourceApplicationError):
    """A source changed after the caller read its revision."""


class SourceRootChangeConflictError(SourceApplicationError):
    """A populated source cannot be repointed at a different root."""


class InvalidSourceRootError(SourceApplicationError):
    """A configured root is malformed, unsafe or outside approved roots."""


class UnsupportedSourceKindError(SourceApplicationError):
    """A local-only operation was requested for a non-local source."""


@dataclass(frozen=True, slots=True)
class SourceAvailabilityResult:
    """Sanitized result returned by a source gateway without raw OS failures."""

    availability: SourceAvailability
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if (self.error_code is None) != (self.error_message is None):
            raise ValueError("availability error code and message must both be present or absent")
        if self.availability is SourceAvailability.AVAILABLE and self.error_code is not None:
            raise ValueError("available source result must not contain an error")
        if self.availability is not SourceAvailability.AVAILABLE and self.error_code is None:
            raise ValueError("unavailable source result must contain a sanitized error")


class LocalSourceGateway(Protocol):
    """Validate and minimally test one local directory without enumerating media."""

    def validate_root(self, configured_root: str) -> str: ...

    def check(self, configured_root: str) -> SourceAvailabilityResult: ...


class SourceRepository(Protocol):
    """Pure-value source persistence used inside a caller-owned unit of work."""

    def add(self, source: MediaSource) -> None: ...

    def get_by_id(self, source_id: MediaSourceId) -> MediaSource | None: ...

    def list(self) -> tuple[MediaSource, ...]: ...

    def update(self, source: MediaSource, expected_revision: int) -> bool: ...

    def has_media_files(self, source_id: MediaSourceId) -> bool: ...


class SourceUnitOfWork(AbstractContextManager["SourceUnitOfWork"], Protocol):
    """Short transaction boundary owned by source application services."""

    @property
    def repository(self) -> SourceRepository: ...

    def __enter__(self) -> Self: ...

    def commit(self) -> None: ...


SourceUnitOfWorkFactory = Callable[[], SourceUnitOfWork]
SourceIdFactory = Callable[[], MediaSourceId]


class LocalSourceService:
    """Explicit create/read/edit/check/enable/disable/retire use cases."""

    def __init__(
        self,
        unit_of_work_factory: SourceUnitOfWorkFactory,
        gateway: LocalSourceGateway,
        clock: Clock,
        id_factory: SourceIdFactory,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._gateway = gateway
        self._clock = clock
        self._id_factory = id_factory

    def create_local_source(
        self,
        display_name: str,
        configured_root: str,
        *,
        enabled: bool,
        source_id: MediaSourceId | None = None,
    ) -> MediaSource:
        normalized_root = self._gateway.validate_root(configured_root)
        source = MediaSource(
            id=source_id or self._id_factory(),
            kind=MediaSourceKind.LOCAL,
            display_name=display_name,
            configured_root=normalized_root,
            enabled=enabled,
        )
        with self._unit_of_work_factory() as unit_of_work:
            if unit_of_work.repository.get_by_id(source.id) is not None:
                raise SourceAlreadyExistsError(f"source {source.id.value!r} already exists")
            unit_of_work.repository.add(source)
            unit_of_work.commit()
        return source

    def get_source(self, source_id: MediaSourceId) -> MediaSource:
        with self._unit_of_work_factory() as unit_of_work:
            return _require_source(unit_of_work.repository, source_id)

    def list_sources(self) -> tuple[MediaSource, ...]:
        with self._unit_of_work_factory() as unit_of_work:
            return unit_of_work.repository.list()

    def update_local_source(
        self,
        source_id: MediaSourceId,
        expected_revision: int,
        *,
        display_name: str,
        configured_root: str | None = None,
    ) -> MediaSource:
        with self._unit_of_work_factory() as unit_of_work:
            original = _require_source(unit_of_work.repository, source_id)
        _require_local_active(original)
        normalized_root = (
            original.configured_root
            if configured_root is None
            else self._gateway.validate_root(configured_root)
        )
        if normalized_root is None:
            raise InvalidSourceRootError("local source has no configured root")

        with self._unit_of_work_factory() as unit_of_work:
            current = _require_source(unit_of_work.repository, source_id)
            _require_revision(current, expected_revision)
            if current.revision != original.revision:
                raise SourceRevisionConflictError(f"source {source_id.value!r} changed during edit")
            if (
                normalized_root != current.configured_root
                and unit_of_work.repository.has_media_files(source_id)
            ):
                raise SourceRootChangeConflictError(
                    "source root cannot change while media files reference the source"
                )
            updated = replace(
                current,
                display_name=display_name,
                configured_root=normalized_root,
                revision=current.revision + 1,
            )
            _store_revision_checked(unit_of_work, updated, current.revision)
            return updated

    def check_availability(self, source_id: MediaSourceId) -> MediaSource:
        with self._unit_of_work_factory() as unit_of_work:
            original = _require_source(unit_of_work.repository, source_id)
        _require_local_active(original)
        if original.configured_root is None:
            raise InvalidSourceRootError("local source has no configured root")
        result = self._gateway.check(original.configured_root)
        checked_at = normalize_utc(self._clock.now(), field_name="source availability check")

        with self._unit_of_work_factory() as unit_of_work:
            current = _require_source(unit_of_work.repository, source_id)
            if current.revision != original.revision:
                raise SourceRevisionConflictError(
                    f"source {source_id.value!r} changed during availability check"
                )
            updated = replace(
                current,
                availability=result.availability,
                last_checked_utc=checked_at,
                current_error_code=result.error_code,
                current_error_message=result.error_message,
                revision=current.revision + 1,
            )
            _store_revision_checked(unit_of_work, updated, current.revision)
            return updated

    def enable_source(self, source_id: MediaSourceId, expected_revision: int) -> MediaSource:
        return self._set_enabled(source_id, expected_revision, enabled=True)

    def disable_source(self, source_id: MediaSourceId, expected_revision: int) -> MediaSource:
        return self._set_enabled(source_id, expected_revision, enabled=False)

    def retire_source(self, source_id: MediaSourceId, expected_revision: int) -> MediaSource:
        with self._unit_of_work_factory() as unit_of_work:
            current = _require_source(unit_of_work.repository, source_id)
            _require_revision(current, expected_revision)
            _require_local_active(current)
            updated = replace(
                current,
                enabled=False,
                retired_utc=normalize_utc(self._clock.now(), field_name="source retirement"),
                revision=current.revision + 1,
            )
            _store_revision_checked(unit_of_work, updated, current.revision)
            return updated

    def _set_enabled(
        self, source_id: MediaSourceId, expected_revision: int, *, enabled: bool
    ) -> MediaSource:
        with self._unit_of_work_factory() as unit_of_work:
            current = _require_source(unit_of_work.repository, source_id)
            _require_revision(current, expected_revision)
            _require_local_active(current)
            updated = replace(current, enabled=enabled, revision=current.revision + 1)
            _store_revision_checked(unit_of_work, updated, current.revision)
            return updated


def _require_source(repository: SourceRepository, source_id: MediaSourceId) -> MediaSource:
    source = repository.get_by_id(source_id)
    if source is None:
        raise SourceNotFoundError(f"source {source_id.value!r} was not found")
    return source


def _require_local_active(source: MediaSource) -> None:
    if source.kind is not MediaSourceKind.LOCAL:
        raise UnsupportedSourceKindError(f"source {source.id.value!r} is not local")
    _require_not_retired(source)


def _require_not_retired(source: MediaSource) -> None:
    if source.retired_utc is not None:
        raise SourceAlreadyRetiredError(f"source {source.id.value!r} is retired")


def _require_revision(source: MediaSource, expected_revision: int) -> None:
    if source.revision != expected_revision:
        raise SourceRevisionConflictError(
            f"source {source.id.value!r} revision {expected_revision} is stale"
        )


def _store_revision_checked(
    unit_of_work: SourceUnitOfWork,
    source: MediaSource,
    expected_revision: int,
) -> None:
    if not unit_of_work.repository.update(source, expected_revision):
        raise SourceRevisionConflictError(f"source {source.id.value!r} changed concurrently")
    unit_of_work.commit()
