"""Identity use cases with short transactions and hashing outside persistence."""

from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Protocol, Self
from uuid import uuid4

from nostalgiabox.domain.catalogue import FilePresenceState, MediaFile, MediaFileId, MediaSourceId
from nostalgiabox.domain.identity import (
    DuplicateReview,
    FingerprintEvidence,
    FingerprintResult,
    IdentityEvidenceKind,
    confirms_duplicate,
    inode_continuity,
)


class StaleIdentityError(RuntimeError):
    """Evidence no longer describes the current observation; transaction must roll back."""


class FingerprintGateway(Protocol):
    def quick(self, path: str, expected: MediaFile) -> FingerprintResult: ...
    def full_sha256(self, path: str, expected: MediaFile) -> FingerprintResult: ...


class IdentityRepository(Protocol):
    def get_file(self, file_id: MediaFileId) -> MediaFile | None: ...
    def guard(self, expected: MediaFile) -> bool: ...
    def source_revision(self, file: MediaFile) -> int | None: ...
    def binding(self, file: MediaFile) -> str: ...
    def evidence(
        self,
        file: MediaFile,
        kind: IdentityEvidenceKind,
        algorithm: str,
        version: int,
    ) -> FingerprintEvidence | None: ...
    def historical_evidence(self, file: MediaFile) -> tuple[FingerprintEvidence, ...]: ...
    def historical_evidence_for_files(
        self, files: tuple[MediaFile, ...]
    ) -> dict[str, tuple[FingerprintEvidence, ...]]:
        """Return immutable fingerprint history keyed by media-file ID."""
        ...

    def add_evidence(self, evidence: FingerprintEvidence) -> None: ...
    def candidates(self, evidence: FingerprintEvidence) -> tuple[FingerprintEvidence, ...]: ...
    def add_candidate(self, left: FingerprintEvidence, right: FingerprintEvidence) -> None: ...
    def reviews(self, file_id: MediaFileId) -> tuple[DuplicateReview, ...]: ...
    def confirmed_group(
        self, left: FingerprintEvidence, right: FingerprintEvidence
    ) -> str | None: ...
    def confirm(self, left: FingerprintEvidence, right: FingerprintEvidence) -> str: ...
    def reconciliation_files(self, source_id: MediaSourceId) -> tuple[MediaFile, ...]:
        """Return active files which are eligible for reconciliation.

        A terminal failed-run discovery remains audit evidence, but must never
        become a predecessor, successor, alias, similarity match, or
        replacement input in a later graph.
        """

    def discoveries(self, source_id: MediaSourceId, generation: int) -> tuple[str, ...]:
        """Return current discoveries plus unresolved rows first seen by an incomplete run."""

    def finalize_provisionals(self, source_id: MediaSourceId, generation: int) -> None:
        """Append resolved/stale terminal records for failed-run discoveries."""

    def transition(
        self,
        old: MediaFile,
        new: MediaFile,
        kind: str,
        reason: str,
        at: datetime,
        *,
        retire: MediaFile | None = None,
    ) -> None: ...
    def move_many(
        self, pairs: tuple[tuple[MediaFile, MediaFile], ...], at: datetime
    ) -> tuple[MediaFile, ...]: ...


class IdentityUnitOfWork(AbstractContextManager["IdentityUnitOfWork"], Protocol):
    @property
    def identities(self) -> IdentityRepository: ...
    def __enter__(self) -> Self: ...
    def commit(self) -> None: ...


class IdentityCoordinator:
    def __init__(
        self,
        factory: Callable[[], IdentityUnitOfWork],
        gateway: FingerprintGateway,
        path_resolver: Callable[[MediaFile], str],
        *,
        confirmation_limit: int = 8,
    ) -> None:
        if confirmation_limit < 1:
            raise ValueError("confirmation limit must be positive")
        self._factory = factory
        self._gateway = gateway
        self._resolve = path_resolver
        self._confirmation_limit = confirmation_limit

    def _policy(self, kind: IdentityEvidenceKind) -> tuple[str, int]:
        return (
            ("sha256", getattr(self._gateway, "full_sha256_version", 1))
            if kind is IdentityEvidenceKind.FULL_SHA256
            else ("sha256-sampled", getattr(self._gateway, "quick_version", 1))
        )

    def inspect(self, file_id: MediaFileId, *, full: bool = False) -> FingerprintEvidence | None:
        kind = IdentityEvidenceKind.FULL_SHA256 if full else IdentityEvidenceKind.QUICK
        policy = self._policy(kind)
        with self._factory() as uow:
            file = uow.identities.get_file(file_id)
            if file is None or file.presence is not FilePresenceState.PRESENT:
                return None
            binding = uow.identities.binding(file)
            cached = uow.identities.evidence(file, kind, *policy)
        if cached is None:
            result = (
                self._gateway.full_sha256(self._resolve(file), file)
                if full
                else self._gateway.quick(self._resolve(file), file)
            )
            if (
                result.kind is not kind
                or result.size_bytes != file.size_bytes
                or (result.algorithm, result.version) != policy
            ):
                raise ValueError("fingerprint result does not match request")
            cached = FingerprintEvidence(str(uuid4()), file.id.value, binding, result)
            with self._factory() as uow:
                if (
                    not uow.identities.guard(file)
                    or uow.identities.binding(file) != binding
                    or self._policy(kind) != policy
                ):
                    raise StaleIdentityError("observation or policy changed during hashing")
                uow.identities.add_evidence(cached)
                for candidate in uow.identities.candidates(cached):
                    uow.identities.add_candidate(cached, candidate)
                uow.commit()
        if kind is IdentityEvidenceKind.QUICK:
            self.confirm_quick_candidates(file.id)
        # Confirmation can run external I/O too; do not return superseded cached evidence.
        with self._factory() as uow:
            current = uow.identities.get_file(file.id)
            if (
                current is None
                or not uow.identities.guard(current)
                or uow.identities.binding(current) != cached.snapshot
                or self._policy(kind) != policy
            ):
                raise StaleIdentityError("inspection evidence is stale")
        return cached

    def confirm_quick_candidates(self, file_id: MediaFileId) -> tuple[str, ...]:
        """Bound new confirmation work after filtering resolved current pairs."""
        kind = IdentityEvidenceKind.FULL_SHA256
        policy = self._policy(kind)
        quick_policy = self._policy(IdentityEvidenceKind.QUICK)
        jobs: list[tuple[MediaFile, str, MediaFile, str]] = []
        with self._factory() as uow:
            left = uow.identities.get_file(file_id)
            if left is None or left.presence is not FilePresenceState.PRESENT:
                return ()
            quick = uow.identities.evidence(left, IdentityEvidenceKind.QUICK, *quick_policy)
            if quick is None:
                return ()
            seen: set[str] = set()
            for candidate in sorted(
                uow.identities.candidates(quick), key=lambda item: (item.media_file_id, item.id)
            ):
                right = uow.identities.get_file(MediaFileId(candidate.media_file_id))
                if (
                    right is None
                    or right.presence is not FilePresenceState.PRESENT
                    or right.id.value in seen
                    or uow.identities.binding(right) != candidate.snapshot
                ):
                    continue
                seen.add(right.id.value)
                left_full = uow.identities.evidence(left, kind, *policy)
                right_full = uow.identities.evidence(right, kind, *policy)
                if left_full is not None and right_full is not None:
                    # Persisted unequal full hashes resolve this observation/policy pair
                    # without spending the bounded budget again.
                    if not confirms_duplicate(left_full.result, right_full.result):
                        continue
                    if uow.identities.confirmed_group(left_full, right_full) is not None:
                        continue
                jobs.append((left, quick.snapshot, right, candidate.snapshot))
                if len(jobs) == self._confirmation_limit:
                    break
        groups: list[str] = []
        for old_left, left_binding, old_right, right_binding in jobs:
            # inspect uses persisted evidence for the shared member, including across calls.
            left_full = self.inspect(old_left.id, full=True)
            right_full = self.inspect(old_right.id, full=True)
            with self._factory() as uow:
                if (
                    left_full is None
                    or right_full is None
                    or left_full.snapshot != left_binding
                    or right_full.snapshot != right_binding
                    or not uow.identities.guard(old_left)
                    or not uow.identities.guard(old_right)
                    or uow.identities.binding(old_left) != left_binding
                    or uow.identities.binding(old_right) != right_binding
                    or self._policy(kind) != policy
                    or self._policy(IdentityEvidenceKind.QUICK) != quick_policy
                ):
                    raise StaleIdentityError("quick candidate changed during full confirmation")
                if confirms_duplicate(left_full.result, right_full.result):
                    groups.append(uow.identities.confirm(left_full, right_full))
                uow.commit()
        return tuple(groups)

    def reviews(self, file_id: MediaFileId) -> tuple[DuplicateReview, ...]:
        with self._factory() as uow:
            return uow.identities.reviews(file_id)

    def confirm_duplicates(self, left_id: MediaFileId, right_id: MediaFileId) -> str:
        if left_id == right_id:
            raise ValueError("duplicate confirmation requires two distinct locations")
        policy = self._policy(IdentityEvidenceKind.FULL_SHA256)
        left = self.inspect(left_id, full=True)
        right = self.inspect(right_id, full=True)
        if left is None or right is None or not confirms_duplicate(left.result, right.result):
            raise ValueError("duplicate confirmation requires equal versioned full SHA-256")
        with self._factory() as uow:
            if self._policy(IdentityEvidenceKind.FULL_SHA256) != policy or any(
                (e.result.algorithm, e.result.version) != policy for e in (left, right)
            ):
                raise StaleIdentityError("duplicate policy changed during confirmation")
            for evidence in (left, right):
                file = uow.identities.get_file(MediaFileId(evidence.media_file_id))
                if (
                    file is None
                    or not uow.identities.guard(file)
                    or uow.identities.binding(file) != evidence.snapshot
                ):
                    raise StaleIdentityError("duplicate evidence is stale")
            group = uow.identities.confirm(left, right)
            uow.commit()
            return group


def reconcile_completed_scan(
    repository: IdentityRepository, source_id: MediaSourceId, generation: int, at: datetime
) -> tuple[MediaFile, ...]:
    """Reconcile each completed scan's independent inode graph components."""
    # Keep every reconciliation predecessor/candidate path inside this one
    # eligibility universe. Terminal provisional discoveries are audit-only,
    # not dormant identities waiting to be resurrected.
    files = repository.reconciliation_files(source_id)
    missing = tuple(file for file in files if file.presence is FilePresenceState.MISSING)
    discovered = repository.discoveries(source_id, generation)
    fresh = tuple(
        file
        for file in files
        if file.id.value in discovered
        and file.presence is FilePresenceState.PRESENT
        and file.last_seen_generation == generation
    )
    graph = {
        new.id.value: tuple(
            old
            for old in missing
            if inode_continuity(old, new)
            and old.normalized_relative_locator != new.normalized_relative_locator
        )
        for new in fresh
    }
    reverse: dict[str, list[MediaFile]] = {}
    for new in fresh:
        for old in graph[new.id.value]:
            reverse.setdefault(old.id.value, []).append(new)
    # Historical evidence is append-only during this transaction. Load it once
    # for the same eligibility universe as the graph, rather than issuing a
    # query for every new/file pair below.
    history_by_file = repository.historical_evidence_for_files(files)
    files_by_id = {file.id.value: file for file in files}
    evidence_by_content_key: dict[tuple[str, int, str, int], list[FingerprintEvidence]] = {}
    for evidence in (evidence for history in history_by_file.values() for evidence in history):
        evidence_by_content_key.setdefault(evidence.result.content_key, []).append(evidence)
    attention: list[MediaFile] = []
    accepted_by_new: dict[str, tuple[MediaFile, MediaFile]] = {}
    for new in fresh:
        candidates = graph[new.id.value]
        new_history = history_by_file.get(new.id.value, ())
        # Files without history cannot have historical similarity. In
        # particular, do not perform a lookup that would only produce an empty
        # result for each newly discovered file.
        similar = (
            tuple(
                candidate
                for evidence in new_history
                for candidate in evidence_by_content_key[evidence.result.content_key]
                if candidate.media_file_id != new.id.value
            )
            if new_history
            else ()
        )
        similar_ids = {evidence.media_file_id for evidence in similar}
        if not candidates and not similar:
            continue
        aliases = tuple(
            file
            for file in files
            if file.presence is FilePresenceState.PRESENT and inode_continuity(file, new)
        )
        conflict = any(
            left.result.content_key != right.result.content_key
            for old in candidates
            for left in history_by_file.get(old.id.value, ())
            for right in new_history
            if (left.result.algorithm, left.result.version)
            == (right.result.algorithm, right.result.version)
        )
        if (
            len(candidates) == 1
            and len(reverse[candidates[0].id.value]) == 1
            and len(aliases) == 1
            and similar_ids <= {candidates[0].id.value}
            and not conflict
        ):
            accepted_by_new[new.id.value] = (candidates[0], new)
        else:
            attention.append(new)
            related = {old.id.value: old for old in candidates}
            for evidence in similar:
                if other := files_by_id.get(evidence.media_file_id):
                    related[other.id.value] = other
            for old in related.values():
                repository.transition(
                    old, new, "needs_attention", "ambiguous_or_weak_similarity", at
                )
    moved: list[tuple[MediaFile, MediaFile]] = []
    for component in _reconciliation_components(fresh, graph):
        pairs = tuple(
            accepted_by_new[new.id.value] for new in component if new.id.value in accepted_by_new
        )
        if not pairs:
            continue
        # move_many remains atomic per component; a protected member cannot leak a partial cycle.
        blocked = repository.move_many(pairs, at)
        if blocked:
            attention.extend(new for new in component if new.id.value in accepted_by_new)
            for old, new in pairs:
                repository.transition(old, new, "needs_attention", "protected_reference", at)
        else:
            moved.extend(pairs)
    moved_old = {old.id.value for old, _ in moved}
    moved_new = {new.id.value for _, new in moved}
    for new in fresh:
        if new.id.value in moved_new or new.id.value in accepted_by_new:
            continue
        same_locator = tuple(
            old
            for old in missing
            if old.id.value not in moved_old
            and old.normalized_relative_locator == new.normalized_relative_locator
        )
        if len(same_locator) == 1 and not graph[new.id.value]:
            repository.transition(
                same_locator[0],
                new,
                "replacement",
                "completed_scan_changed_locator",
                at,
                retire=same_locator[0],
            )
    # A completed enumeration is authoritative for each failed-run discovery:
    # a row seen here is resolved, while an unseen or retired row is stale.
    # Neither may enter another reconciliation graph.
    repository.finalize_provisionals(source_id, generation)
    return tuple(attention)


def _reconciliation_components(
    fresh: tuple[MediaFile, ...], graph: dict[str, tuple[MediaFile, ...]]
) -> tuple[tuple[MediaFile, ...], ...]:
    """Return components of the inode graph plus locator dependencies.

    An inode edge describes the candidate rename itself. A locator dependency
    links it to the provisional observation occupying an old locator, keeping
    swaps and longer cycles in one atomic ``move_many`` call.
    """
    by_old: dict[str, list[MediaFile]] = {}
    by_new = {new.id.value: new for new in fresh}
    by_locator: dict[str, list[MediaFile]] = {}
    for new in fresh:
        by_locator.setdefault(new.normalized_relative_locator, []).append(new)
        for old in graph[new.id.value]:
            by_old.setdefault(old.id.value, []).append(new)
    adjacency: dict[str, set[str]] = {key: set() for key in by_new}
    for new in fresh:
        for old in graph[new.id.value]:
            for other in (
                *by_old[old.id.value],
                *by_locator.get(old.normalized_relative_locator, ()),
            ):
                adjacency[new.id.value].add(other.id.value)
                adjacency[other.id.value].add(new.id.value)
    seen: set[str] = set()
    components: list[tuple[MediaFile, ...]] = []
    for start in sorted(by_new):
        if start in seen:
            continue
        stack = [start]
        component: list[MediaFile] = []
        while stack:
            key = stack.pop()
            if key in seen:
                continue
            seen.add(key)
            component.append(by_new[key])
            stack.extend(sorted(adjacency[key] - seen, reverse=True))
        components.append(tuple(sorted(component, key=lambda file: file.id.value)))
    return tuple(components)
