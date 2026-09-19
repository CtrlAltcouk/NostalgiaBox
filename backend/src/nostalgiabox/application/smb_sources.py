"""Managed SMB lifecycle behind narrow secret and OS-mount ports.

No CIFS client, subprocess invocation, password serialization, or mount options live here.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Protocol

from nostalgiabox.application.sources import (
    LocalSourceGateway,
    LocalSourceService,
    SourceAlreadyExistsError,
    SourceAlreadyRetiredError,
    SourceAvailabilityResult,
    SourceIdFactory,
    SourceNotFoundError,
    SourceRevisionConflictError,
    SourceUnitOfWorkFactory,
    _require_not_retired,
    _require_revision,
    _store_revision_checked,
)
from nostalgiabox.domain.catalogue import (
    MediaSource,
    MediaSourceId,
    MediaSourceKind,
    SmbShareConfig,
)
from nostalgiabox.domain.clock import Clock
from nostalgiabox.domain.time import normalize_utc


@dataclass(frozen=True, slots=True, repr=False)
class SmbCredential:
    """Ephemeral credential supplied only to the secret-store write operation."""

    username: str
    password: str


class SecretStore(Protocol):
    """Root-owned credential storage. Secret reads are intentionally unavailable."""

    def put(self, credential_ref: str, credential: SmbCredential) -> None: ...

    def delete(self, credential_ref: str) -> None: ...


class ManagedMountGateway(Protocol):
    """Typed bridge to a reviewed OS helper; results must already be sanitized."""

    def provision(
        self, source_id: MediaSourceId, config: SmbShareConfig, credential_ref: str, enabled: bool
    ) -> SourceAvailabilityResult: ...
    def replace(
        self, source_id: MediaSourceId, config: SmbShareConfig, credential_ref: str, enabled: bool
    ) -> SourceAvailabilityResult: ...
    def enable(self, source_id: MediaSourceId) -> SourceAvailabilityResult: ...
    def disable(self, source_id: MediaSourceId) -> None: ...
    def reconnect(self, source_id: MediaSourceId) -> SourceAvailabilityResult: ...
    def retire(self, source_id: MediaSourceId) -> None: ...
    def check(self, source_id: MediaSourceId) -> SourceAvailabilityResult: ...


CredentialRefFactory = Callable[[], str]


def managed_mount_path(source_id: MediaSourceId) -> str:
    """Return the only path managed SMB sources can expose to scanners/players."""
    if not source_id.value or any(
        c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_"
        for c in source_id.value
    ):
        raise ValueError("source id is not safe for derived mount path")
    return f"/run/nostalgiabox/media/{source_id.value}"


class ManagedSmbSourceService(LocalSourceService):
    """Use cases whose external effects compensate in reverse dependency order."""

    def __init__(
        self,
        unit_of_work_factory: SourceUnitOfWorkFactory,
        gateway: LocalSourceGateway,
        clock: Clock,
        id_factory: SourceIdFactory,
        *,
        secrets: SecretStore,
        mounts: ManagedMountGateway,
        credential_ref_factory: CredentialRefFactory,
    ) -> None:
        super().__init__(unit_of_work_factory, gateway, clock, id_factory)
        self._secrets = secrets
        self._mounts = mounts
        self._credential_ref_factory = credential_ref_factory

    def create_smb_source(
        self,
        display_name: str,
        config: SmbShareConfig,
        credential: SmbCredential,
        *,
        enabled: bool,
        source_id: MediaSourceId | None = None,
    ) -> MediaSource:
        identifier = source_id or self._id_factory()
        credential_ref = self._credential_ref_factory()
        source = MediaSource(
            id=identifier,
            kind=MediaSourceKind.SMB,
            display_name=display_name,
            configured_root=managed_mount_path(identifier),
            enabled=enabled,
            smb_config=config,
            credential_ref=credential_ref,
        )
        mounted = False
        secret_written = False
        try:
            self._secrets.put(credential_ref, credential)
            secret_written = True
            result = self._mounts.provision(identifier, config, credential_ref, enabled)
            mounted = True
            source = self._with_availability(source, result)
            with self._unit_of_work_factory() as unit_of_work:
                if unit_of_work.repository.get_by_id(identifier) is not None:
                    raise SourceAlreadyExistsError("source already exists")
                unit_of_work.repository.add(source)
                unit_of_work.commit()
            return source
        except Exception:
            if mounted:
                self._mounts.retire(identifier)
            if secret_written:
                self._secrets.delete(credential_ref)
            raise

    def replace_smb_credential(
        self, source_id: MediaSourceId, expected_revision: int, credential: SmbCredential
    ) -> MediaSource:
        original = self._get_active_smb(source_id, expected_revision)
        assert original.smb_config is not None and original.credential_ref is not None
        replacement_ref = self._credential_ref_factory()
        secret_written = False
        replaced = False
        try:
            self._secrets.put(replacement_ref, credential)
            secret_written = True
            result = self._mounts.replace(
                source_id, original.smb_config, replacement_ref, original.enabled
            )
            replaced = True
            updated = self._persist_external_result(
                original, result, credential_ref=replacement_ref, increment_revision=True
            )
        except Exception:
            if replaced:
                self._mounts.replace(
                    source_id, original.smb_config, original.credential_ref, original.enabled
                )
            if secret_written:
                self._secrets.delete(replacement_ref)
            raise
        self._secrets.delete(original.credential_ref)
        return updated

    def check_smb_availability(self, source_id: MediaSourceId) -> MediaSource:
        source = self._get_active_smb(source_id)
        return self._persist_external_result(source, self._mounts.check(source_id))

    def reconnect_smb_source(self, source_id: MediaSourceId, expected_revision: int) -> MediaSource:
        source = self._get_active_smb(source_id, expected_revision)
        if not source.enabled:
            raise SourceAlreadyRetiredError("disabled SMB source cannot reconnect")
        return self._persist_external_result(source, self._mounts.reconnect(source_id))

    def enable_smb_source(self, source_id: MediaSourceId, expected_revision: int) -> MediaSource:
        source = self._get_active_smb(source_id, expected_revision)
        result = self._mounts.enable(source_id)
        try:
            return self._persist_external_result(
                source, result, enabled=True, increment_revision=True
            )
        except Exception:
            self._mounts.disable(source_id)
            raise

    def disable_smb_source(self, source_id: MediaSourceId, expected_revision: int) -> MediaSource:
        source = self._get_active_smb(source_id, expected_revision)
        self._mounts.disable(source_id)
        try:
            return self._persist_external_result(
                source, None, enabled=False, increment_revision=True
            )
        except Exception:
            assert source.smb_config is not None and source.credential_ref is not None
            self._mounts.replace(
                source_id, source.smb_config, source.credential_ref, source.enabled
            )
            raise

    def retire_smb_source(self, source_id: MediaSourceId, expected_revision: int) -> MediaSource:
        source = self._get_active_smb(source_id, expected_revision)
        self._mounts.retire(source_id)
        try:
            with self._unit_of_work_factory() as unit_of_work:
                current = unit_of_work.repository.get_by_id(source_id)
                if current is None:
                    raise SourceNotFoundError("source was not found")
                _require_revision(current, expected_revision)
                updated = replace(
                    current,
                    enabled=False,
                    retired_utc=normalize_utc(self._clock.now(), field_name="source retirement"),
                    revision=current.revision + 1,
                )
                _store_revision_checked(unit_of_work, updated, current.revision)
        except Exception:
            assert source.smb_config is not None and source.credential_ref is not None
            self._mounts.provision(
                source_id, source.smb_config, source.credential_ref, source.enabled
            )
            raise
        assert source.credential_ref is not None
        self._secrets.delete(source.credential_ref)
        return updated

    def _get_active_smb(
        self, source_id: MediaSourceId, expected_revision: int | None = None
    ) -> MediaSource:
        source = self.get_source(source_id)
        if source.kind is not MediaSourceKind.SMB:
            raise SourceNotFoundError("source is not SMB")
        _require_not_retired(source)
        if source.smb_config is None or source.credential_ref is None:
            raise SourceNotFoundError("source is not a managed SMB source")
        if expected_revision is not None:
            _require_revision(source, expected_revision)
        return source

    def _persist_external_result(
        self,
        original: MediaSource,
        result: SourceAvailabilityResult | None,
        *,
        enabled: bool | None = None,
        credential_ref: str | None = None,
        increment_revision: bool = False,
    ) -> MediaSource:
        checked_at = normalize_utc(self._clock.now(), field_name="SMB source availability check")
        with self._unit_of_work_factory() as unit_of_work:
            current = unit_of_work.repository.get_by_id(original.id)
            if current is None:
                raise SourceNotFoundError("source was not found")
            if current.revision != original.revision:
                raise SourceRevisionConflictError("source changed during SMB operation")
            updated = replace(
                current,
                enabled=current.enabled if enabled is None else enabled,
                credential_ref=current.credential_ref if credential_ref is None else credential_ref,
                availability=current.availability if result is None else result.availability,
                last_checked_utc=current.last_checked_utc if result is None else checked_at,
                current_error_code=current.current_error_code
                if result is None
                else result.error_code,
                current_error_message=current.current_error_message
                if result is None
                else result.error_message,
                revision=current.revision + 1 if increment_revision else current.revision,
            )
            _store_revision_checked(unit_of_work, updated, current.revision)
            return updated

    @staticmethod
    def _with_availability(source: MediaSource, result: SourceAvailabilityResult) -> MediaSource:
        return replace(
            source,
            availability=result.availability,
            current_error_code=result.error_code,
            current_error_message=result.error_message,
        )
