"""Managed SMB lifecycle tests with non-secret fake adapters."""

from datetime import UTC, datetime
from types import TracebackType

import pytest

from nostalgiabox.application.smb_sources import (
    ManagedSmbSourceService,
    SmbCredential,
    managed_mount_path,
)
from nostalgiabox.application.sources import SourceAlreadyExistsError, SourceAvailabilityResult
from nostalgiabox.domain.catalogue import (
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    SmbShareConfig,
    SourceAvailability,
)
from tests.support.clock import FakeClock


class _Repository:
    def __init__(self) -> None:
        self.sources: dict[MediaSourceId, MediaSource] = {}
        self.populated: set[MediaSourceId] = set()

    def add(self, source: MediaSource) -> None:
        self.sources[source.id] = source

    def get_by_id(self, source_id: MediaSourceId) -> MediaSource | None:
        return self.sources.get(source_id)

    def list(self) -> tuple[MediaSource, ...]:
        return tuple(self.sources.values())

    def update(self, source: MediaSource, expected_revision: int) -> bool:
        current = self.sources.get(source.id)
        if current is None or current.revision != expected_revision:
            return False
        self.sources[source.id] = source
        return True

    def has_media_files(self, source_id: MediaSourceId) -> bool:
        return source_id in self.populated


class _UnitOfWork:
    def __init__(self, repository: _Repository) -> None:
        self.repository = repository

    def __enter__(self) -> "_UnitOfWork":
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


class _Secrets:
    def __init__(self) -> None:
        self.values: dict[str, SmbCredential] = {}
        self.calls: list[tuple[str, str]] = []

    def put(self, credential_ref: str, credential: SmbCredential) -> None:
        self.values[credential_ref] = credential
        self.calls.append(("put", credential_ref))

    def delete(self, credential_ref: str) -> None:
        self.values.pop(credential_ref, None)
        self.calls.append(("delete", credential_ref))


class _Mounts:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def provision(
        self, source_id: MediaSourceId, config: SmbShareConfig, credential_ref: str, enabled: bool
    ) -> SourceAvailabilityResult:
        self.calls.append(("provision", source_id.value))
        return SourceAvailabilityResult(SourceAvailability.AVAILABLE)

    def replace(
        self, source_id: MediaSourceId, config: SmbShareConfig, credential_ref: str, enabled: bool
    ) -> SourceAvailabilityResult:
        self.calls.append(("replace", credential_ref))
        return SourceAvailabilityResult(SourceAvailability.AVAILABLE)

    def enable(self, source_id: MediaSourceId) -> SourceAvailabilityResult:
        self.calls.append(("enable", source_id.value))
        return SourceAvailabilityResult(SourceAvailability.AVAILABLE)

    def disable(self, source_id: MediaSourceId) -> None:
        self.calls.append(("disable", source_id.value))

    def reconnect(self, source_id: MediaSourceId) -> SourceAvailabilityResult:
        self.calls.append(("reconnect", source_id.value))
        return SourceAvailabilityResult(SourceAvailability.AVAILABLE)

    def retire(self, source_id: MediaSourceId) -> None:
        self.calls.append(("retire", source_id.value))

    def check(self, source_id: MediaSourceId) -> SourceAvailabilityResult:
        self.calls.append(("check", source_id.value))
        return SourceAvailabilityResult(SourceAvailability.AVAILABLE)


def _service() -> tuple[ManagedSmbSourceService, _Repository, _Secrets, _Mounts]:
    repository = _Repository()
    secrets = _Secrets()
    mounts = _Mounts()
    service = ManagedSmbSourceService(
        lambda: _UnitOfWork(repository),
        _Gateway(),
        FakeClock(datetime(2026, 9, 18, tzinfo=UTC)),
        lambda: MediaSourceId("generated-smb"),
        secrets=secrets,
        mounts=mounts,
        credential_ref_factory=iter(("cred-1", "cred-2")).__next__,
    )
    return service, repository, secrets, mounts


class _Gateway:
    def validate_root(self, configured_root: str) -> str:
        return configured_root

    def check(self, configured_root: str) -> SourceAvailabilityResult:
        return SourceAvailabilityResult(SourceAvailability.AVAILABLE)


def test_managed_smb_lifecycle_never_persists_password() -> None:
    service, repository, secrets, mounts = _service()
    config = SmbShareConfig("nas.example", "archive", "films")
    credential = SmbCredential("reader", "super-secret")

    source = service.create_smb_source("NAS", config, credential, enabled=True)
    assert source.configured_root == managed_mount_path(source.id)
    assert source.smb_config == config
    assert source.credential_ref == "cred-1"
    assert repository.sources[source.id] == source
    assert "super-secret" not in repr(source)
    assert "super-secret" not in repr(mounts.calls)

    replaced = service.replace_smb_credential(
        source.id, source.revision, SmbCredential("reader2", "new-secret")
    )
    assert replaced.credential_ref == "cred-2"
    assert "cred-1" not in secrets.values
    assert secrets.values["cred-2"].password == "new-secret"

    disabled = service.disable_smb_source(replaced.id, replaced.revision)
    assert disabled.enabled is False
    enabled = service.enable_smb_source(disabled.id, disabled.revision)
    assert enabled.enabled is True
    retired = service.retire_smb_source(enabled.id, enabled.revision)
    assert retired.enabled is False
    assert retired.retired_utc is not None
    assert secrets.values == {}
    assert [name for name, _ in mounts.calls] == [
        "provision",
        "replace",
        "disable",
        "enable",
        "retire",
    ]


def test_create_smb_conflict_compensates_mount_and_secret() -> None:
    service, repository, secrets, mounts = _service()
    source_id = MediaSourceId("existing")
    repository.sources[source_id] = MediaSource(
        id=source_id,
        kind=MediaSourceKind.SMB,
        display_name="Existing",
        configured_root=managed_mount_path(source_id),
        enabled=False,
        smb_config=SmbShareConfig("nas.example", "archive"),
        credential_ref="old-ref",
    )

    with pytest.raises(SourceAlreadyExistsError):
        service.create_smb_source(
            "Duplicate",
            SmbShareConfig("nas.example", "archive"),
            SmbCredential("reader", "secret"),
            enabled=True,
            source_id=source_id,
        )

    assert "cred-1" not in secrets.values
    assert [name for name, _ in mounts.calls] == ["provision", "retire"]


def test_mount_path_rejects_path_unsafe_source_id() -> None:
    with pytest.raises(ValueError):
        managed_mount_path(MediaSourceId("bad/id"))
