"""Task 3.5 conservative identity, scan integration and stale-write regression tests."""

import hashlib
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import Engine, Row, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from nostalgiabox.application.identity import (
    IdentityCoordinator,
    StaleIdentityError,
    reconcile_completed_scan,
)
from nostalgiabox.application.scans import ScanCoordinator
from nostalgiabox.domain.catalogue import FilePresenceState, MediaFile, MediaFileId
from nostalgiabox.domain.identity import (
    FingerprintEvidence,
    FingerprintResult,
    IdentityEvidenceKind,
)
from nostalgiabox.domain.scanning import ScanIssueId, ScanKind, ScanRunId, ScanStatus
from nostalgiabox.persistence.identity_repositories import SqlAlchemyIdentityRepository
from nostalgiabox.persistence.models import (
    ContentFingerprintRecord,
    ContentGroupMemberRecord,
    ContentGroupRecord,
    DuplicateCandidateRecord,
    IdentityDiscoveryResolutionRecord,
    IdentityRetirementRecord,
    IdentityTransitionRecord,
    MediaFileRecord,
)
from nostalgiabox.persistence.scan_repositories import SqlAlchemyMediaInventoryRepository
from nostalgiabox.persistence.scan_uow import SqlAlchemyScanUnitOfWork
from tests.integration.test_scan_coordinator import (
    _START,
    _AvailableGateway,
    _completed,
    _coordinator,
    _InlineExecutor,
    _issue_codes,
    _MutableTraversal,
    _observation,
    _run,
    _store_source,
)
from tests.support.clock import FakeClock


def _factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _present(factory: sessionmaker[Session]) -> tuple[MediaFile, ...]:
    with factory() as session:
        repo = SqlAlchemyIdentityRepository(session)
        rows = session.scalars(select(MediaFileRecord)).all()
        return tuple(
            file
            for row in rows
            if (file := repo.get_file(MediaFileId(row.id))) is not None
            and file.presence is FilePresenceState.PRESENT
        )


def test_scan_rename_preserves_established_id_and_immutable_observations(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    clock = FakeClock(_START)
    traversal = _MutableTraversal([_observation("old.mkv", 3, 10)])
    scanner = _coordinator(factory, traversal, _AvailableGateway(), _InlineExecutor(), clock)
    _completed(scanner, factory, source.id, ScanKind.FULL)
    old = _present(factory)[0]
    clock.advance(timedelta(seconds=1))
    traversal.events = [_observation("new.mkv", 3, 10)]
    _completed(scanner, factory, source.id, ScanKind.FULL)
    current = _present(factory)
    assert len(current) == 1
    assert current[0].id == old.id
    assert current[0].normalized_relative_locator == "new.mkv"
    assert current[0].first_observed_utc == old.first_observed_utc
    with factory() as session:
        transition = session.scalar(select(IdentityTransitionRecord))
        assert transition is not None and transition.kind == "confident_rename"
        assert "old.mkv" in transition.predecessor_snapshot
        assert "new.mkv" in transition.successor_snapshot
        assert session.scalar(select(func.count()).select_from(IdentityRetirementRecord)) == 1
    _completed(scanner, factory, source.id, ScanKind.FULL)
    assert _present(factory)[0].id == old.id


def test_completed_rescan_reconciles_failed_provisional_rename_once(
    persistence_engine: Engine,
) -> None:
    """A failed enumeration never decides identity, but its provisional can recover."""
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    clock = FakeClock(_START)
    traversal = _MutableTraversal([_observation("old.mkv", 3, 10)])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), clock, batch_size=1
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    established = _present(factory)[0]

    clock.advance(timedelta(seconds=1))
    traversal.events = [_observation("new.mkv", 3, 10), _observation("never.mkv", 1, 1)]
    traversal.failure_after = 1
    failed = scanner.start_scan(source.id, ScanKind.FULL)
    assert _run(factory, failed.id).status is ScanStatus.FAILED
    provisional = next(
        file for file in _present(factory) if file.normalized_relative_locator == "new.mkv"
    )
    assert provisional.id != established.id

    traversal.failure_after = None
    traversal.events = [_observation("new.mkv", 3, 10)]
    completed = _completed(scanner, factory, source.id, ScanKind.FULL)
    assert completed.status is ScanStatus.COMPLETED
    recovered = _present(factory)
    assert [(file.id, file.normalized_relative_locator) for file in recovered] == [
        (established.id, "new.mkv")
    ]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityTransitionRecord)) == 1
        assert session.scalar(select(func.count()).select_from(IdentityRetirementRecord)) == 1
        resolution = session.scalar(select(IdentityDiscoveryResolutionRecord))
        assert resolution is not None and resolution.lifecycle == "stale"
    # Re-running finalisation is a no-op: no duplicate identity or transition appears.
    scanner._finalize(completed.id)
    assert _present(factory)[0].id == established.id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityTransitionRecord)) == 1

        assert (
            session.scalar(select(func.count()).select_from(IdentityDiscoveryResolutionRecord)) == 1
        )


def test_terminal_stale_provisional_cannot_reenter_missing_predecessors_or_retries(
    persistence_engine: Engine,
) -> None:
    """A sealed failed discovery is audit-only, even when it later becomes missing."""
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("old.mkv", 3, 10)])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START), batch_size=1
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    established = _present(factory)[0]

    traversal.events = [_observation("failed.mkv", 3, 10), _observation("never.mkv", 1, 1)]
    traversal.failure_after = 1
    assert (
        _run(factory, scanner.start_scan(source.id, ScanKind.FULL).id).status is ScanStatus.FAILED
    )
    stale = next(file for file in _present(factory) if file.id != established.id)

    traversal.failure_after = None
    traversal.events = []
    _completed(scanner, factory, source.id, ScanKind.FULL)
    with factory() as session:
        resolution = session.get(IdentityDiscoveryResolutionRecord, stale.id.value)
        assert resolution is not None and resolution.lifecycle == "stale"

    traversal.events = [_observation("recovered.mkv", 3, 10)]
    recovered_run = _completed(scanner, factory, source.id, ScanKind.FULL)
    assert [(file.id, file.normalized_relative_locator) for file in _present(factory)] == [
        (established.id, "recovered.mkv")
    ]
    _completed(scanner, factory, source.id, ScanKind.FULL)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityTransitionRecord)) == 1
        resolution = session.get(IdentityDiscoveryResolutionRecord, stale.id.value)
        assert resolution is not None and resolution.lifecycle == "stale"
        assert resolution.authoritative_generation < _run(factory, recovered_run.id).generation


def test_terminal_resolved_provisional_cannot_reenter_reconciliation(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal(
        [_observation("failed.mkv", 3, 10), _observation("never.mkv", 1, 1)]
    )
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START), batch_size=1
    )
    traversal.failure_after = 1
    assert (
        _run(factory, scanner.start_scan(source.id, ScanKind.FULL).id).status is ScanStatus.FAILED
    )
    resolved = _present(factory)[0]

    traversal.failure_after = None
    traversal.events = [_observation("failed.mkv", 3, 10)]
    _completed(scanner, factory, source.id, ScanKind.FULL)
    traversal.events = []
    _completed(scanner, factory, source.id, ScanKind.FULL)
    traversal.events = [_observation("later.mkv", 3, 10)]
    _completed(scanner, factory, source.id, ScanKind.FULL)
    present = _present(factory)
    assert len(present) == 1 and present[0].id != resolved.id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityTransitionRecord)) == 0
        resolution = session.get(IdentityDiscoveryResolutionRecord, resolved.id.value)
        assert resolution is not None and resolution.lifecycle == "resolved"


def test_completed_rescan_keeps_genuinely_new_failed_provisional_identity(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("new.mkv", 3, 10), _observation("never.mkv", 1, 1)])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START), batch_size=1
    )
    traversal.failure_after = 1
    failed = scanner.start_scan(source.id, ScanKind.FULL)
    assert _run(factory, failed.id).status is ScanStatus.FAILED
    provisional = _present(factory)[0]

    traversal.failure_after = None
    traversal.events = [_observation("new.mkv", 3, 10)]
    _completed(scanner, factory, source.id, ScanKind.FULL)
    assert _present(factory)[0].id == provisional.id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityTransitionRecord)) == 0
        resolution = session.scalar(select(IdentityDiscoveryResolutionRecord))
        assert resolution is not None and resolution.lifecycle == "resolved"


@pytest.mark.parametrize("change", ["size", "mtime", "inode"])
def test_same_locator_changed_observation_creates_successor(
    persistence_engine: Engine, change: str
) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    observation = _observation("same.mkv", 3, 10)
    traversal = _MutableTraversal([observation])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    old = _present(factory)[0]
    traversal.events = [
        replace(observation, size_bytes=4)
        if change == "size"
        else replace(observation, modified_time_ns=11)
        if change == "mtime"
        else replace(observation, inode_id=999)
    ]
    _completed(scanner, factory, source.id, ScanKind.FULL)
    new = _present(factory)[0]
    assert new.id != old.id
    with factory() as session:
        transition = session.scalar(select(IdentityTransitionRecord))
        assert transition is not None and transition.kind == "replacement"
        assert transition.predecessor_id == old.id.value
        assert transition.successor_id == new.id.value
        assert SqlAlchemyIdentityRepository(session).get_file(old.id) is None
        old_row = session.get(MediaFileRecord, old.id.value)
        assert old_row is not None and old_row.size_bytes == old.size_bytes
    _completed(scanner, factory, source.id, ScanKind.FULL)
    assert _present(factory)[0].id == new.id


@pytest.mark.parametrize(
    "old_names,new_names",
    [
        (["old.mkv"], ["a.mkv", "b.mkv"]),
        (["old-a.mkv", "old-b.mkv"], ["new.mkv"]),
    ],
)
def test_ambiguous_inode_never_merges(
    persistence_engine: Engine, old_names: list[str], new_names: list[str]
) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation(name, 3, 10) for name in old_names])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    old_ids = {file.id for file in _present(factory)}
    traversal.events = [_observation(name, 3, 10) for name in new_names]
    run = _completed(scanner, factory, source.id, ScanKind.FULL)
    assert old_ids.isdisjoint(file.id for file in _present(factory))
    assert "file.possible_duplicate" in _issue_codes(factory, run.id)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityRetirementRecord)) == 0


def test_changed_ambiguous_contexts_preserve_immutable_history_and_idempotency(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("old.mkv", 3, 10)])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)

    # Context A is genuinely ambiguous: one missing predecessor has two
    # inode-continuous successors. Its evidence must remain historical.
    traversal.events = [_observation("a-left.mkv", 3, 10), _observation("a-right.mkv", 3, 10)]
    _completed(scanner, factory, source.id, ScanKind.FULL)

    def decisions() -> tuple[Row[tuple[str, str, str, str, str, str]], ...]:
        with factory() as session:
            return tuple(
                session.execute(
                    select(
                        IdentityTransitionRecord.id,
                        IdentityTransitionRecord.kind,
                        IdentityTransitionRecord.predecessor_id,
                        IdentityTransitionRecord.successor_id,
                        IdentityTransitionRecord.predecessor_snapshot,
                        IdentityTransitionRecord.successor_snapshot,
                    ).order_by(IdentityTransitionRecord.id)
                ).all()
            )

    context_a = decisions()
    assert len(context_a) == 2
    assert {decision[1] for decision in context_a} == {"needs_attention"}
    _completed(scanner, factory, source.id, ScanKind.FULL)
    assert decisions() == context_a

    # Context B changes the ambiguous physical context, rather than changing
    # one successor into a same-locator replacement. It creates new immutable
    # Needs Attention evidence while retaining all of A.
    traversal.events = [_observation("b-left.mkv", 3, 10), _observation("b-right.mkv", 3, 10)]
    _completed(scanner, factory, source.id, ScanKind.FULL)
    context_b = decisions()
    assert set(context_a).issubset(context_b)
    assert len(context_b) > len(context_a)
    assert {decision[1] for decision in context_b} == {"needs_attention"}
    assert any(
        decision[3] not in {old[3] for old in context_a}
        for decision in context_b
        if decision not in context_a
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    assert decisions() == context_b


def test_present_old_locator_is_a_copy_not_a_rename(persistence_engine: Engine) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("old.mkv", 3, 10)])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    old = _present(factory)[0]
    traversal.events.append(_observation("copy.mkv", 3, 10))
    _completed(scanner, factory, source.id, ScanKind.FULL)
    assert len(_present(factory)) == 2
    assert old.id in {f.id for f in _present(factory)}


class _Gateway:
    def __init__(self, *, version: int = 1) -> None:
        self.calls = 0
        self.version = version
        self.callback: Callable[[], None] = lambda: None

    @property
    def full_sha256_version(self) -> int:
        return self.version

    def quick(self, path: str, expected: MediaFile) -> FingerprintResult:
        self.calls += 1
        self.callback()
        assert expected.size_bytes is not None
        return FingerprintResult(
            IdentityEvidenceKind.QUICK, "sha256-sampled", 1, "a" * 64, expected.size_bytes
        )

    def full_sha256(self, path: str, expected: MediaFile) -> FingerprintResult:
        self.calls += 1
        self.callback()
        assert expected.size_bytes is not None
        return FingerprintResult(
            IdentityEvidenceKind.FULL_SHA256,
            "sha256",
            self.version,
            hashlib.sha256(path.encode()).hexdigest(),
            expected.size_bytes,
        )


def _seed_pair(
    factory: sessionmaker[Session], *, cross_source: bool = False
) -> tuple[MediaFile, MediaFile]:
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("a.mkv", 3, 10), _observation("b.mkv", 3, 10)])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    left, right = sorted(_present(factory), key=lambda file: file.normalized_relative_locator)
    if cross_source:
        other = _store_source(factory, "other")
        right = replace(right, source_id=other.id)
        with factory() as session:
            SqlAlchemyMediaInventoryRepository(session).store(right)
            session.commit()
    return left, right


def test_quick_candidates_cross_source_full_confirmation_and_idempotency(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory, cross_source=True)
    gateway = _Gateway()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda file: "same bytes"
    )
    service.inspect(left.id)
    service.inspect(right.id)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(DuplicateCandidateRecord)) == 2
        assert session.scalar(select(func.count()).select_from(ContentGroupRecord)) == 1
    group = service.confirm_duplicates(left.id, right.id)
    assert service.confirm_duplicates(left.id, right.id) == group
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ContentGroupMemberRecord)) == 2
    assert len(_present(factory)) == 2
    calls_after_confirmation = gateway.calls
    assert service.inspect(right.id) is not None
    assert gateway.calls == calls_after_confirmation


def _seed_three(factory: sessionmaker[Session]) -> tuple[MediaFile, MediaFile, MediaFile]:
    source = _store_source(factory)
    traversal = _MutableTraversal(
        [_observation("a.mkv", 3, 10), _observation("b.mkv", 3, 10), _observation("c.mkv", 3, 10)]
    )
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    return tuple(sorted(_present(factory), key=lambda file: file.normalized_relative_locator))  # type: ignore[return-value]


def test_shared_member_confirmations_reuse_pending_and_persisted_membership(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    a, b, c = _seed_three(factory)
    gateway = _Gateway()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda file: "same bytes"
    )
    evidence = {file.id: service.inspect(file.id, full=True) for file in (a, b, c)}
    assert all(value is not None for value in evidence.values())
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        left = evidence[a.id]
        middle = evidence[b.id]
        right = evidence[c.id]
        assert left is not None and middle is not None and right is not None
        group = uow.identities.confirm(left, middle)
        # Autoflush is disabled for the UoW. Simulate a membership just queued by
        # another confirmation path and verify confirm() reuses it without a
        # second insert or a uniqueness failure at commit.
        uow.identities._session.add(  # pyright: ignore[reportPrivateUsage]
            ContentGroupMemberRecord(group_id=group, evidence_id=right.id)
        )
        assert uow.identities.confirm(left, right) == group
        assert uow.identities.confirm(left, middle) == group
        uow.commit()
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ContentGroupRecord)) == 1
        assert session.scalar(select(func.count()).select_from(ContentGroupMemberRecord)) == 3
    assert service.confirm_duplicates(a.id, c.id) == group


def test_quick_confirmation_caches_shared_full_evidence_once_per_invocation(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    a, b, c = _seed_three(factory)
    gateway = _Gateway()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda file: "same bytes"
    )
    for file in (a, b, c):
        service.inspect(file.id)
    # Three quick samples and exactly one full read for each A/B/C observation;
    # A's fresh full evidence is shared by the A-B and A-C confirmations.
    assert gateway.calls == 6
    assert service.confirm_quick_candidates(a.id) == ()
    assert gateway.calls == 6


def test_full_evidence_cache_invalidates_changed_observation_and_policy(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    a, _, _ = _seed_three(factory)
    gateway = _Gateway()

    def resolve(file: MediaFile) -> str:
        return "same bytes"

    service = IdentityCoordinator(lambda: SqlAlchemyScanUnitOfWork(factory), gateway, resolve)
    service.inspect(a.id, full=True)
    assert gateway.calls == 1
    with factory() as session:
        SqlAlchemyMediaInventoryRepository(session).store(replace(a, modified_time_ns=11))
        session.commit()
    service.inspect(a.id, full=True)
    assert gateway.calls == 2
    gateway.version = 2
    service.inspect(a.id, full=True)
    assert gateway.calls == 3
    service.inspect(a.id, full=True)
    assert gateway.calls == 3


def test_confirmation_limit_applies_after_stale_candidates_are_filtered(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    a, b, c = _seed_three(factory)
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        for file in (a, b, c):
            uow.identities.add_evidence(
                FingerprintEvidence(
                    str(uuid4()),
                    file.id.value,
                    uow.identities.binding(file),
                    FingerprintResult(IdentityEvidenceKind.QUICK, "sha256-sampled", 1, "a" * 64, 3),
                )
            )
        uow.inventory.store(
            replace(b, presence=FilePresenceState.MISSING, missing_since_utc=_START)
        )
        uow.commit()
    gateway = _Gateway()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory),
        gateway,
        lambda file: "same bytes",
        confirmation_limit=1,
    )
    groups = service.confirm_quick_candidates(a.id)
    assert len(groups) == 1
    # B sorts before C but is missing, so it cannot consume A's one-candidate budget.
    assert gateway.calls == 2


def test_quick_collision_does_not_confirm_different_full_hashes(persistence_engine: Engine) -> None:
    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), _Gateway(), lambda file: file.id.value
    )
    service.inspect(left.id)
    service.inspect(right.id)
    with pytest.raises(ValueError, match="full SHA-256"):
        service.confirm_duplicates(left.id, right.id)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ContentGroupRecord)) == 0


def test_unchanged_rescans_reuse_evidence_and_keep_groups_current(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("a.mkv", 3, 10), _observation("b.mkv", 3, 10)])
    gateway = _Gateway()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda _: "same bytes"
    )
    scanner = ScanCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory),
        _AvailableGateway(),
        traversal,
        _InlineExecutor(),
        FakeClock(_START),
        lambda: ScanRunId(str(uuid4())),
        lambda: ScanIssueId(str(uuid4())),
        lambda: MediaFileId(str(uuid4())),
        persistence_batch_size=1,
        progress_update_threshold=1,
        identity_inspector=service.inspect,
    )

    _completed(scanner, factory, source.id, ScanKind.FULL)
    files = _present(factory)
    evidence = {file.id: service.inspect(file.id) for file in files}
    assert gateway.calls == 4
    assert all(
        review.current and review.confirmed_group_id
        for file in files
        for review in service.reviews(file.id)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    _completed(scanner, factory, source.id, ScanKind.FULL)
    assert gateway.calls == 4
    assert {file.id: service.inspect(file.id) for file in files} == evidence
    assert all(
        review.current and review.confirmed_group_id
        for file in files
        for review in service.reviews(file.id)
    )
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        current = uow.sources.get_by_id(source.id)
        assert current is not None and current.revision == source.revision


@pytest.mark.parametrize("full", [False, True])
@pytest.mark.parametrize("field", ["size", "inode", "missing"])
def test_hash_read_rejects_stale_discovery_atomically(
    persistence_engine: Engine, field: str, full: bool
) -> None:
    factory = _factory(persistence_engine)
    left, _ = _seed_pair(factory)
    gateway = _Gateway()

    def mutate() -> None:
        with factory() as session:
            changed = (
                replace(left, size_bytes=99)
                if field == "size"
                else replace(left, inode_id=999)
                if field == "inode"
                else replace(left, presence=FilePresenceState.MISSING, missing_since_utc=_START)
            )
            SqlAlchemyMediaInventoryRepository(session).store(changed)
            session.commit()

    gateway.callback = mutate
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda file: "same"
    )
    with pytest.raises(StaleIdentityError):
        service.inspect(left.id, full=full)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ContentFingerprintRecord)) == 0


def test_confirmation_rejects_first_file_changed_while_second_hashes(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    gateway = _Gateway()

    def mutate() -> None:
        if gateway.calls == 2:
            with factory() as session:
                SqlAlchemyMediaInventoryRepository(session).store(replace(left, size_bytes=99))
                session.commit()

    gateway.callback = mutate
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda file: "same"
    )
    with pytest.raises(StaleIdentityError):
        service.confirm_duplicates(left.id, right.id)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ContentGroupRecord)) == 0


def test_scan_projects_weak_candidate_issues_without_merging(persistence_engine: Engine) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("a.mkv", 3, 10)])
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), _Gateway(), lambda file: "same"
    )
    scanner = ScanCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory),
        _AvailableGateway(),
        traversal,
        _InlineExecutor(),
        FakeClock(_START),
        lambda: ScanRunId(str(uuid4())),
        lambda: ScanIssueId(str(uuid4())),
        lambda: MediaFileId(str(uuid4())),
        persistence_batch_size=1,
        progress_update_threshold=1,
        identity_inspector=service.inspect,
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    old = _present(factory)[0]
    traversal.events = [replace(_observation("b.mkv", 3, 10), inode_id=999)]
    run = _completed(scanner, factory, source.id, ScanKind.FULL)
    assert _present(factory)[0].id != old.id
    assert "file.possible_duplicate" in _issue_codes(factory, run.id)
    with factory() as session:
        # Scan completion is bookkeeping; current equal full evidence may be grouped
        # without changing either physical identity.
        assert session.scalar(select(func.count()).select_from(ContentGroupRecord)) == 1


def test_stale_transition_rolls_back_without_retirement(persistence_engine: Engine) -> None:
    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    with factory() as session:
        SqlAlchemyMediaInventoryRepository(session).store(replace(left, size_bytes=99))
        session.commit()
    with SqlAlchemyScanUnitOfWork(factory) as uow, pytest.raises(StaleIdentityError):
        uow.identities.transition(left, right, "replacement", "test", _START, retire=left)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityTransitionRecord)) == 0
        assert session.scalar(select(func.count()).select_from(IdentityRetirementRecord)) == 0


@pytest.mark.parametrize("kind", list(IdentityEvidenceKind))
def test_conflicting_content_vetoes_inode_rename(
    persistence_engine: Engine, kind: IdentityEvidenceKind
) -> None:
    from nostalgiabox.application.identity import reconcile_completed_scan
    from nostalgiabox.domain.identity import FingerprintEvidence

    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        for index, file in enumerate((left, right)):
            uow.identities.add_evidence(
                FingerprintEvidence(
                    str(uuid4()),
                    file.id.value,
                    uow.identities.binding(file),
                    FingerprintResult(
                        kind,
                        "sha256" if kind is IdentityEvidenceKind.FULL_SHA256 else "sha256-sampled",
                        1,
                        str(index) * 64,
                        3,
                    ),
                )
            )
        uow.inventory.store(
            replace(left, presence=FilePresenceState.MISSING, missing_since_utc=_START)
        )
        uow.commit()
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        attention = reconcile_completed_scan(uow.identities, left.source_id, 1, _START)
        assert attention == (right,)
        uow.commit()
    assert _present(factory)[0].id == right.id
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityRetirementRecord)) == 0


def test_full_hash_alone_is_reviewable_and_never_preserves_id(persistence_engine: Engine) -> None:
    from nostalgiabox.application.identity import reconcile_completed_scan

    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    right = replace(right, inode_id=999)
    with factory() as session:
        SqlAlchemyMediaInventoryRepository(session).store(right)
        session.commit()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), _Gateway(), lambda file: "same"
    )
    service.inspect(left.id, full=True)
    service.inspect(right.id, full=True)
    assert service.reviews(right.id)[0].needs_attention
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        uow.inventory.store(
            replace(left, presence=FilePresenceState.MISSING, missing_since_utc=_START)
        )
        uow.commit()
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        assert tuple(
            f.id for f in reconcile_completed_scan(uow.identities, left.source_id, 1, _START)
        ) == (right.id,)
        uow.commit()
    assert _present(factory)[0].id == right.id


def test_review_projection_distinguishes_confirmed_and_stale_history(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), _Gateway(), lambda file: "same"
    )
    service.inspect(left.id)
    service.inspect(right.id)
    assert not service.reviews(left.id)[0].needs_attention
    group = service.confirm_duplicates(left.id, right.id)
    assert all(
        r.confirmed_group_id == group and not r.needs_attention for r in service.reviews(left.id)
    )
    with factory() as session:
        SqlAlchemyMediaInventoryRepository(session).store(replace(left, size_bytes=99))
        session.commit()
    reviews = service.reviews(left.id)
    assert reviews and all(not r.current and not r.needs_attention for r in reviews)


def test_provisional_rendition_prevents_rename_and_reports_attention(
    persistence_engine: Engine,
) -> None:
    from nostalgiabox.application.identity import reconcile_completed_scan
    from nostalgiabox.persistence.models import CatalogueItemRecord, PlayableRenditionRecord

    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    with factory() as session:
        session.add(CatalogueItemRecord(id="editorial"))
        session.flush()
        session.add(
            PlayableRenditionRecord(
                id="rendition",
                catalogue_item_id="editorial",
                media_file_id=right.id.value,
                segment_start_us=0,
                segment_duration_us=1,
                logical_playable_duration_us=1,
                is_whole_file=True,
                preferred=True,
            )
        )
        SqlAlchemyMediaInventoryRepository(session).store(
            replace(left, presence=FilePresenceState.MISSING, missing_since_utc=_START)
        )
        session.commit()
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        assert tuple(
            f.id for f in reconcile_completed_scan(uow.identities, left.source_id, 1, _START)
        ) == (right.id,)
        uow.commit()
    assert _present(factory)[0].id == right.id


def test_generated_local_rename_copy_replace_preserves_media_bytes(
    persistence_engine: Engine, tmp_path: Path
) -> None:
    from nostalgiabox.fingerprint.local import LocalFingerprintAdapter
    from nostalgiabox.source.local import LocalFilesystemSourceGateway
    from nostalgiabox.source.traversal import LocalFilesystemTraversalGateway

    root = tmp_path / "media"
    root.mkdir()
    old_path = root / "old.mkv"
    old_path.write_bytes(b"generated fixture" * 100)
    factory = _factory(persistence_engine)
    source = _store_source(factory, configured_root=str(root))
    source_gateway = LocalFilesystemSourceGateway([str(root)])
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory),
        LocalFingerprintAdapter(),
        lambda file: str(root / file.original_relative_locator),
    )
    scanner = ScanCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory),
        source_gateway,
        LocalFilesystemTraversalGateway(source_gateway, (".mkv",)),
        _InlineExecutor(),
        FakeClock(_START),
        lambda: ScanRunId(str(uuid4())),
        lambda: ScanIssueId(str(uuid4())),
        lambda: MediaFileId(str(uuid4())),
        persistence_batch_size=1,
        progress_update_threshold=1,
        identity_inspector=service.inspect,
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    old = _present(factory)[0]
    new_path = root / "new.mkv"
    old_path.rename(new_path)  # Test fixture operation, never application behavior.
    _completed(scanner, factory, source.id, ScanKind.FULL)
    assert _present(factory)[0].id == old.id
    copy_path = root / "copy.mkv"
    copy_path.write_bytes(new_path.read_bytes())
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()}
    run = _completed(scanner, factory, source.id, ScanKind.FULL)
    assert "file.possible_duplicate" in _issue_codes(factory, run.id)
    files = _present(factory)
    assert len(files) == 2
    service.confirm_duplicates(files[0].id, files[1].id)
    assert before == {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in root.iterdir()}
    replacement = root / "replacement.tmp"
    replacement.write_bytes(b"different generated content")
    replacement.replace(new_path)
    _completed(scanner, factory, source.id, ScanKind.FULL)
    assert (
        next(f for f in _present(factory) if f.normalized_relative_locator == "new.mkv").id
        != old.id
    )
    assert new_path.read_bytes() == b"different generated content"
    assert copy_path.read_bytes() == before["copy.mkv"][0]


@pytest.mark.parametrize("operation", ["rename", "replacement"])
def test_established_rendition_stays_with_predecessor_identity(
    persistence_engine: Engine, operation: str
) -> None:
    from nostalgiabox.persistence.models import CatalogueItemRecord, PlayableRenditionRecord

    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("old.mkv", 3, 10)])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    old = _present(factory)[0]
    with factory() as session:
        session.add(CatalogueItemRecord(id="editorial"))
        session.flush()
        session.add(
            PlayableRenditionRecord(
                id="rendition",
                catalogue_item_id="editorial",
                media_file_id=old.id.value,
                segment_start_us=0,
                segment_duration_us=1,
                logical_playable_duration_us=1,
                is_whole_file=True,
                preferred=True,
            )
        )
        session.commit()
    traversal.events = [
        _observation("new.mkv", 3, 10) if operation == "rename" else _observation("old.mkv", 4, 11)
    ]
    _completed(scanner, factory, source.id, ScanKind.FULL)
    current = _present(factory)[0]
    assert (current.id == old.id) is (operation == "rename")
    with factory() as session:
        rendition = session.get(PlayableRenditionRecord, "rendition")
        assert rendition is not None and rendition.media_file_id == old.id.value
        assert session.scalar(select(func.count()).select_from(PlayableRenditionRecord)) == 1


def test_failed_enumeration_does_not_infer_rename(persistence_engine: Engine) -> None:
    from nostalgiabox.domain.scanning import ScanStatus
    from tests.integration.test_scan_coordinator import _run

    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("old.mkv", 3, 10)])
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    old = _present(factory)[0]
    traversal.events = [_observation("new.mkv", 3, 10), _observation("other.mkv", 4, 11)]
    traversal.failure_after = 1
    queued = scanner.start_scan(source.id, ScanKind.FULL)
    assert _run(factory, queued.id).status is ScanStatus.FAILED
    assert old in _present(factory)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityTransitionRecord)) == 0


@pytest.mark.parametrize(
    ("locators", "rotated_inodes"),
    [(("a.mkv", "b.mkv"), (20, 10)), (("a.mkv", "b.mkv", "c.mkv"), (20, 30, 10))],
)
def test_completed_scan_reconciles_locator_cycles_atomically(
    persistence_engine: Engine, locators: tuple[str, ...], rotated_inodes: tuple[int, ...]
) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal(
        [
            replace(_observation(locator, 3, 10), inode_id=(index + 1) * 10)
            for index, locator in enumerate(locators)
        ]
    )
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    established = {file.inode_id: file.id for file in _present(factory)}
    traversal.events = [
        replace(_observation(locator, 3, 10), inode_id=inode)
        for locator, inode in zip(locators, rotated_inodes, strict=True)
    ]
    _completed(scanner, factory, source.id, ScanKind.FULL)
    current = {file.normalized_relative_locator: file.id for file in _present(factory)}
    assert current == {
        locator: established[inode] for locator, inode in zip(locators, rotated_inodes, strict=True)
    }
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(IdentityRetirementRecord)) == len(
            locators
        )


def test_reconciliation_components_keep_locator_swaps_atomic(
    persistence_engine: Engine,
) -> None:
    from nostalgiabox.application.identity import _reconciliation_components

    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    old_a = replace(left, inode_id=10, presence=FilePresenceState.MISSING, missing_since_utc=_START)
    old_b = replace(
        right, inode_id=20, presence=FilePresenceState.MISSING, missing_since_utc=_START
    )
    fresh_a = replace(
        right,
        id=MediaFileId(str(uuid4())),
        normalized_relative_locator="a.mkv",
        original_relative_locator="a.mkv",
        inode_id=20,
        last_seen_generation=2,
    )
    fresh_b = replace(
        left,
        id=MediaFileId(str(uuid4())),
        normalized_relative_locator="b.mkv",
        original_relative_locator="b.mkv",
        inode_id=10,
        last_seen_generation=2,
    )

    components = _reconciliation_components(
        (fresh_a, fresh_b), {fresh_a.id.value: (old_b,), fresh_b.id.value: (old_a,)}
    )

    assert len(components) == 1
    assert set(components[0]) == {fresh_a, fresh_b}


def test_completed_scan_keeps_non_bijective_inode_evidence_reviewable(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal(
        [_observation("a.mkv", 3, 10), replace(_observation("b.mkv", 3, 10), inode_id=20)]
    )
    scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(scanner, factory, source.id, ScanKind.FULL)
    traversal.events = [_observation("c.mkv", 3, 10), _observation("d.mkv", 3, 10)]
    run = _completed(scanner, factory, source.id, ScanKind.FULL)
    assert "file.possible_duplicate" in _issue_codes(factory, run.id)


def test_three_completed_rescans_reuse_durable_evidence_without_hashing(
    persistence_engine: Engine,
) -> None:
    """Generation changes protect scan enumeration, not content evidence validity."""
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    traversal = _MutableTraversal([_observation("single.mkv", 3, 10)])
    initial_scanner = _coordinator(
        factory, traversal, _AvailableGateway(), _InlineExecutor(), FakeClock(_START)
    )
    _completed(initial_scanner, factory, source.id, ScanKind.FULL)
    file = _present(factory)[0]
    gateway = _Gateway()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda _: "same bytes"
    )
    evidence = service.inspect(file.id)
    assert evidence is not None and gateway.calls == 1
    scanner = ScanCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory),
        _AvailableGateway(),
        traversal,
        _InlineExecutor(),
        FakeClock(_START),
        lambda: ScanRunId(str(uuid4())),
        lambda: ScanIssueId(str(uuid4())),
        lambda: MediaFileId(str(uuid4())),
        persistence_batch_size=1,
        progress_update_threshold=1,
        identity_inspector=service.inspect,
    )

    for _ in range(3):
        _completed(scanner, factory, source.id, ScanKind.FULL)

    assert gateway.calls == 1  # Zero reads across all three later scan generations.
    current = _present(factory)[0]
    assert current.id == file.id and current.last_seen_generation == 4
    assert service.inspect(current.id) == evidence


@pytest.mark.parametrize("full", [False, True])
def test_new_generation_reuses_evidence_with_unchanged_cheap_fields_even_in_flight(
    persistence_engine: Engine, full: bool
) -> None:
    """A generation-only write must neither invalidate nor reject a hash in flight."""
    factory = _factory(persistence_engine)
    left, _ = _seed_pair(factory)
    gateway = _Gateway()

    def advance_generation_only() -> None:
        with factory() as session:
            SqlAlchemyMediaInventoryRepository(session).store(replace(left, last_seen_generation=2))
            session.commit()

    gateway.callback = advance_generation_only
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda _: "same"
    )
    evidence = service.inspect(left.id, full=full)
    assert evidence is not None and gateway.calls == 1
    assert service.inspect(left.id, full=full) == evidence
    assert gateway.calls == 1


@pytest.mark.parametrize("file_count", [10, 100, 1000])
@pytest.mark.parametrize("mixed_history", [False, True], ids=["no-history", "mixed-history"])
def test_reconciliation_history_queries_are_bounded_and_preserve_empty_outcome(
    persistence_engine: Engine, file_count: int, mixed_history: bool
) -> None:
    """Generated coverage guards against reintroducing per-file evidence SELECTs."""
    factory = _factory(persistence_engine)
    source = _store_source(factory)
    files = tuple(
        MediaFile(
            MediaFileId(f"generated-{index}"),
            source.id,
            f"generated-{index}.mkv",
            f"generated-{index}.mkv",
            FilePresenceState.PRESENT,
            1,
            index,
            index + 1,
            index + 1,
            1,
            _START,
            _START,
        )
        for index in range(file_count)
    )
    with factory() as session:
        inventory = SqlAlchemyMediaInventoryRepository(session)
        for file in files:
            inventory.store(file)
        if mixed_history:
            session.add_all(
                ContentFingerprintRecord(
                    id=f"generated-evidence-{file.id.value}",
                    media_file_id=file.id.value,
                    snapshot="historical",
                    kind=IdentityEvidenceKind.QUICK.value,
                    algorithm="sha256-sampled",
                    version=1,
                    digest=f"{index:064x}",
                    size_bytes=1,
                )
                for index, file in enumerate(files)
                if index % 2 == 0
            )
        session.commit()

    with factory() as session:
        repository = SqlAlchemyIdentityRepository(session)
        # The bulk API must retain the legacy per-file contents and ordering.
        expected_history = {file.id.value: repository.historical_evidence(file) for file in files}
        assert repository.historical_evidence_for_files(files) == expected_history

    statements: list[str] = []

    def count_queries(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        statements.append(statement)

    event.listen(persistence_engine, "before_cursor_execute", count_queries)
    try:
        with SqlAlchemyScanUnitOfWork(factory) as uow:
            assert reconcile_completed_scan(uow.identities, source.id, 1, _START) == ()
            uow.commit()
    finally:
        event.remove(persistence_engine, "before_cursor_execute", count_queries)

    history_selects = [statement for statement in statements if "content_fingerprints" in statement]
    # 500-ID chunks: 10/100 use one history SELECT; 1000 uses two. The
    # reconciliation has no historical evidence query inside its per-file loop.
    assert len(history_selects) == (file_count + 499) // 500
    assert len(statements) == 3 + (file_count + 499) // 500
