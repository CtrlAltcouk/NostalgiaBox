"""Local source lifecycle application-service tests."""

from dataclasses import replace
from datetime import UTC, datetime
from types import TracebackType

import pytest

from nostalgiabox.application.sources import (
    LocalSourceService,
    SourceAlreadyRetiredError,
    SourceAvailabilityResult,
    SourceNotFoundError,
    SourceRevisionConflictError,
    SourceRootChangeConflictError,
    UnsupportedSourceKindError,
)
from nostalgiabox.domain.catalogue import (
    InvalidMediaSourceError,
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    SourceAvailability,
)
from tests.support.clock import FakeClock


def test_create_local_source_has_stable_identity_and_no_scan_or_availability_claim() -> None:
    service, repository, _ = _service()

    source = service.create_local_source(
        "Family Videos",
        "/approved/family",
        enabled=True,
    )

    assert source.id == MediaSourceId("generated-source")
    assert source.display_name == "Family Videos"
    assert source.configured_root == "/approved/family"
    assert source.enabled is True
    assert source.availability is SourceAvailability.UNKNOWN
    assert source.last_checked_utc is None
    assert source.last_successful_scan_utc is None
    assert repository.sources[source.id] == source


def test_blank_display_name_is_rejected() -> None:
    service, _, _ = _service()

    with pytest.raises(InvalidMediaSourceError, match="display name"):
        service.create_local_source(" ", "/approved/family", enabled=False)


def test_name_and_unpopulated_root_edit_preserve_identity() -> None:
    service, _, gateway = _service()
    source = service.create_local_source("Old", "/approved/old", enabled=True)
    gateway.normalized_roots["/approved/new"] = "/approved/new"

    updated = service.update_local_source(
        source.id,
        source.revision,
        display_name="New",
        configured_root="/approved/new",
    )

    assert updated.id == source.id
    assert updated.display_name == "New"
    assert updated.configured_root == "/approved/new"
    assert updated.revision == 2


def test_root_edit_is_rejected_after_media_file_reference_exists() -> None:
    service, repository, gateway = _service()
    source = service.create_local_source("Source", "/approved/old", enabled=True)
    repository.populated.add(source.id)
    gateway.normalized_roots["/approved/new"] = "/approved/new"

    with pytest.raises(SourceRootChangeConflictError, match="cannot change"):
        service.update_local_source(
            source.id,
            source.revision,
            display_name="Source",
            configured_root="/approved/new",
        )


def test_enabled_availability_and_retirement_are_independent() -> None:
    service, _, gateway = _service()
    source = service.create_local_source("Source", "/approved/source", enabled=True)
    gateway.results.append(
        SourceAvailabilityResult(
            SourceAvailability.UNAVAILABLE,
            "source.unavailable",
            "Source unavailable.",
        )
    )

    unavailable = service.check_availability(source.id)
    assert unavailable.enabled is True
    disabled = service.disable_source(source.id, unavailable.revision)
    assert disabled.availability is SourceAvailability.UNAVAILABLE
    enabled = service.enable_source(source.id, disabled.revision)
    assert enabled.availability is SourceAvailability.UNAVAILABLE
    retired = service.retire_source(source.id, enabled.revision)
    assert retired.enabled is False
    assert retired.retired_utc == datetime(2026, 8, 10, 12, tzinfo=UTC)

    with pytest.raises(SourceAlreadyRetiredError, match="retired"):
        service.enable_source(source.id, retired.revision)


def test_successful_check_uses_clock_clears_error_and_preserves_last_scan() -> None:
    service, repository, gateway = _service()
    source = service.create_local_source("Source", "/approved/source", enabled=False)
    scan_time = datetime(2026, 8, 9, 10, tzinfo=UTC)
    repository.sources[source.id] = replace(
        source,
        availability=SourceAvailability.PERMISSION_DENIED,
        current_error_code="source.permission_denied",
        current_error_message="Cannot read source.",
        last_successful_scan_utc=scan_time,
    )
    gateway.results.append(SourceAvailabilityResult(SourceAvailability.AVAILABLE))

    checked = service.check_availability(source.id)

    assert checked.last_checked_utc == datetime(2026, 8, 10, 12, tzinfo=UTC)
    assert checked.availability is SourceAvailability.AVAILABLE
    assert checked.current_error_code is None
    assert checked.current_error_message is None
    assert checked.last_successful_scan_utc == scan_time
    assert checked.enabled is False


@pytest.mark.parametrize(
    ("availability", "code"),
    [
        (SourceAvailability.PERMISSION_DENIED, "source.permission_denied"),
        (SourceAvailability.INVALID_ROOT, "source.invalid_root"),
        (SourceAvailability.UNAVAILABLE, "source.unavailable"),
    ],
)
def test_structured_gateway_failures_persist_without_raw_os_errors(
    availability: SourceAvailability,
    code: str,
) -> None:
    service, _, gateway = _service()
    source = service.create_local_source("Source", "/approved/source", enabled=True)
    gateway.results.append(
        SourceAvailabilityResult(availability, code, "Sanitized source diagnostic.")
    )

    checked = service.check_availability(source.id)

    assert checked.availability is availability
    assert checked.current_error_code == code
    assert checked.current_error_message == "Sanitized source diagnostic."


def test_stale_revision_and_change_during_external_check_are_rejected() -> None:
    service, repository, gateway = _service()
    source = service.create_local_source("Source", "/approved/source", enabled=True)

    with pytest.raises(SourceRevisionConflictError, match="stale"):
        service.disable_source(source.id, 99)

    def mutate_during_check() -> None:
        current = repository.sources[source.id]
        repository.sources[source.id] = replace(current, revision=current.revision + 1)

    gateway.on_check = mutate_during_check
    gateway.results.append(SourceAvailabilityResult(SourceAvailability.AVAILABLE))
    with pytest.raises(SourceRevisionConflictError, match="changed during"):
        service.check_availability(source.id)


def test_missing_and_non_local_sources_fail_explicitly() -> None:
    service, repository, _ = _service()

    with pytest.raises(SourceNotFoundError, match="not found"):
        service.get_source(MediaSourceId("missing"))

    smb = MediaSource(MediaSourceId("smb"), MediaSourceKind.SMB, display_name="NAS")
    repository.sources[smb.id] = smb
    with pytest.raises(UnsupportedSourceKindError, match="not local"):
        service.check_availability(smb.id)
    with pytest.raises(UnsupportedSourceKindError, match="not local"):
        service.enable_source(smb.id, smb.revision)


def test_get_and_list_return_pure_sources_in_stable_order() -> None:
    service, repository, _ = _service()
    second = MediaSource(MediaSourceId("z-source"), MediaSourceKind.SMB, display_name="NAS")
    first = MediaSource(MediaSourceId("a-source"), MediaSourceKind.SMB, display_name="Archive")
    repository.sources = {second.id: second, first.id: first}

    assert service.get_source(first.id) == first
    assert service.list_sources() == (first, second)


class _FakeGateway:
    def __init__(self) -> None:
        self.normalized_roots = {
            "/approved/family": "/approved/family",
            "/approved/old": "/approved/old",
            "/approved/source": "/approved/source",
        }
        self.results: list[SourceAvailabilityResult] = []
        self.on_check: object = None

    def validate_root(self, configured_root: str) -> str:
        return self.normalized_roots[configured_root]

    def check(self, configured_root: str) -> SourceAvailabilityResult:
        if callable(self.on_check):
            self.on_check()
        return self.results.pop(0)


class _FakeRepository:
    def __init__(self) -> None:
        self.sources: dict[MediaSourceId, MediaSource] = {}
        self.populated: set[MediaSourceId] = set()

    def add(self, source: MediaSource) -> None:
        self.sources[source.id] = source

    def get_by_id(self, source_id: MediaSourceId) -> MediaSource | None:
        return self.sources.get(source_id)

    def list(self) -> tuple[MediaSource, ...]:
        return tuple(sorted(self.sources.values(), key=lambda source: source.id.value))

    def update(self, source: MediaSource, expected_revision: int) -> bool:
        current = self.sources.get(source.id)
        if current is None or current.revision != expected_revision:
            return False
        self.sources[source.id] = source
        return True

    def has_media_files(self, source_id: MediaSourceId) -> bool:
        return source_id in self.populated


class _FakeUnitOfWork:
    def __init__(self, repository: _FakeRepository) -> None:
        self.repository = repository

    def __enter__(self) -> "_FakeUnitOfWork":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def commit(self) -> None:
        return None


def _service() -> tuple[LocalSourceService, _FakeRepository, _FakeGateway]:
    repository = _FakeRepository()
    gateway = _FakeGateway()
    service = LocalSourceService(
        lambda: _FakeUnitOfWork(repository),
        gateway,
        FakeClock(datetime(2026, 8, 10, 12, tzinfo=UTC)),
        lambda: MediaSourceId("generated-source"),
    )
    return service, repository, gateway
