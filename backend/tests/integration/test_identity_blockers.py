"""Focused regressions for the five Task 3.5 Expert blockers."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from itertools import permutations
from pathlib import Path
from threading import Event

import pytest
from sqlalchemy import Engine, event, func, select, update

from nostalgiabox.application.identity import (
    IdentityCoordinator,
    StaleIdentityError,
    _reconciliation_components,
)
from nostalgiabox.config.settings import Settings
from nostalgiabox.domain.catalogue import FilePresenceState, MediaFile, MediaFileId
from nostalgiabox.domain.identity import (
    FingerprintEvidence,
    FingerprintResult,
    IdentityEvidenceKind,
)
from nostalgiabox.persistence.database import create_engine
from nostalgiabox.persistence.identity_repositories import SqlAlchemyIdentityRepository
from nostalgiabox.persistence.models import (
    Base,
    ContentFingerprintRecord,
    ContentGroupMemberRecord,
    ContentGroupRecord,
    MediaFileRecord,
    MediaSourceRecord,
)
from nostalgiabox.persistence.scan_uow import SqlAlchemyScanUnitOfWork
from tests.integration.test_identity import _factory, _Gateway, _seed_pair, _seed_three


@pytest.mark.parametrize("full", [False, True])
@pytest.mark.parametrize(
    "change",
    [
        {"original_relative_locator": "A.mkv"},
        {"device_id": 999},
        {"revision": 99},
        "source_revision",
        "aba",
    ],
)
def test_hashing_rejects_complete_binding_changes(
    persistence_engine: Engine, full: bool, change: dict[str, object] | str
) -> None:
    factory = _factory(persistence_engine)
    left, _ = _seed_pair(factory)
    gateway = _Gateway()

    def mutate() -> None:
        with factory() as session:
            if change == "source_revision":
                session.execute(
                    update(MediaSourceRecord).values(revision=MediaSourceRecord.revision + 1)
                )
            elif change == "aba":
                for inode in (999, left.inode_id):
                    session.execute(
                        update(MediaFileRecord)
                        .where(MediaFileRecord.id == left.id.value)
                        .values(inode_id=inode)
                    )
            else:
                assert isinstance(change, dict)
                session.execute(
                    update(MediaFileRecord)
                    .where(MediaFileRecord.id == left.id.value)
                    .values(**change)
                )
            session.commit()

    gateway.callback = mutate
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda _: "same"
    )
    with pytest.raises(StaleIdentityError):
        service.inspect(left.id, full=full)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ContentFingerprintRecord)) == 0


def test_persisted_cache_uses_requested_policy_and_rejects_stale_files(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    gateway = _Gateway(version=7)
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda _: "same"
    )
    old = service.inspect(left.id, full=True)
    other = service.inspect(right.id, full=True)
    assert old is not None and other is not None
    assert service.inspect(left.id, full=True) == old
    assert gateway.calls == 2
    with factory() as session:
        repo = SqlAlchemyIdentityRepository(session)
        assert repo.evidence(left, IdentityEvidenceKind.FULL_SHA256, "sha256", 7) == old
        assert repo.evidence(left, IdentityEvidenceKind.FULL_SHA256, "sha256", 1) is None
        assert repo.evidence(left, IdentityEvidenceKind.FULL_SHA256, "sha256-sampled", 7) is None
        session.execute(
            update(MediaFileRecord)
            .where(MediaFileRecord.id == left.id.value)
            .values(modified_time_ns=11)
        )
        session.commit()
    with factory() as session:
        repo = SqlAlchemyIdentityRepository(session)
        assert repo.evidence(left, IdentityEvidenceKind.FULL_SHA256, "sha256", 7) is None
        with pytest.raises(StaleIdentityError):
            repo.confirm(old, other)
    refreshed = service.inspect(left.id, full=True)
    assert refreshed != old and gateway.calls == 3
    with factory() as session:
        session.execute(update(MediaSourceRecord).values(revision=MediaSourceRecord.revision + 1))
        session.commit()
    assert service.inspect(left.id, full=True) != refreshed
    assert gateway.calls == 4
    gateway.version = 8
    newest = service.inspect(left.id, full=True)
    assert newest is not None and newest.result.version == 8
    assert service.inspect(left.id, full=True) == newest
    assert gateway.calls == 5


def test_one_way_locator_dependency_is_order_independent(persistence_engine: Engine) -> None:
    factory = _factory(persistence_engine)
    a, b, c = _seed_three(factory)
    # A -> B -> free locator, plus an independent C -> D rename. In particular,
    # the lexically first node has only an incoming dependency edge.
    fresh_b = replace(a, id=MediaFileId("z"), normalized_relative_locator="b.mkv")
    fresh_free = replace(b, id=MediaFileId("a"), normalized_relative_locator="free.mkv")
    fresh_d = replace(c, id=MediaFileId("m"), normalized_relative_locator="d.mkv")
    graph: dict[str, tuple[MediaFile, ...]] = {
        fresh_b.id.value: (a,),
        fresh_free.id.value: (b,),
        fresh_d.id.value: (c,),
    }
    for ordering in permutations((fresh_b, fresh_free, fresh_d)):
        components = _reconciliation_components(ordering, graph)
        assert tuple(tuple(f.id.value for f in group) for group in components) == (
            ("a", "z"),
            ("m",),
        )


def test_mismatch_budget_progress_and_change_reeligibility(persistence_engine: Engine) -> None:
    factory = _factory(persistence_engine)
    a, b, c = sorted(_seed_three(factory), key=lambda f: f.id.value)

    def seed_quick() -> None:
        with SqlAlchemyScanUnitOfWork(factory) as uow:
            for original in (a, b, c):
                file = uow.identities.get_file(original.id)
                assert file is not None
                uow.identities.add_evidence(
                    FingerprintEvidence(
                        f"quick-{file.id.value}-{file.revision}",
                        file.id.value,
                        uow.identities.binding(file),
                        FingerprintResult(
                            IdentityEvidenceKind.QUICK, "sha256-sampled", 1, "a" * 64, 3
                        ),
                    )
                )
            uow.commit()

    seed_quick()
    gateway = _Gateway()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory),
        gateway,
        lambda file: "collision" if file.id == b.id else "same",
        confirmation_limit=1,
    )
    assert service.confirm_quick_candidates(a.id) == ()
    assert gateway.calls == 2  # First deterministic pair mismatches.
    assert len(service.confirm_quick_candidates(a.id)) == 1
    assert gateway.calls == 3  # Next pair progresses without rereading A/B.
    assert service.confirm_quick_candidates(a.id) == ()
    assert gateway.calls == 3
    gateway.version = 2
    assert service.confirm_quick_candidates(a.id) == ()
    assert gateway.calls == 5  # The mismatch is eligible under the new policy.
    assert len(service.confirm_quick_candidates(a.id)) == 1
    assert gateway.calls == 6
    with factory() as session:
        session.execute(
            update(MediaFileRecord)
            .where(MediaFileRecord.id == b.id.value)
            .values(modified_time_ns=11)
        )
        session.commit()
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        current = uow.identities.get_file(b.id)
        assert current is not None
        uow.identities.add_evidence(
            FingerprintEvidence(
                "changed-quick",
                b.id.value,
                uow.identities.binding(current),
                FingerprintResult(IdentityEvidenceKind.QUICK, "sha256-sampled", 1, "a" * 64, 3),
            )
        )
        uow.commit()
    assert service.confirm_quick_candidates(a.id) == ()
    assert gateway.calls == 7
    assert service.confirm_quick_candidates(a.id) == ()
    assert gateway.calls == 7


@pytest.mark.parametrize("existing_group", [False, True])
def test_competing_sqlite_sessions_confirm_idempotently(
    tmp_path: Path, existing_group: bool
) -> None:
    engine = create_engine(
        Settings(environment="test", database_url=f"sqlite:///{tmp_path / 'race.db'}")
    )
    Base.metadata.create_all(engine)
    factory = _factory(engine)
    a, b, c = _seed_three(factory)
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), _Gateway(), lambda _: "same"
    )
    left, middle, right = (service.inspect(f.id, full=True) for f in (a, b, c))
    assert left is not None and middle is not None and right is not None
    if existing_group:
        service.confirm_duplicates(a.id, b.id)
    writer_holds_lock, competitor_attempted_write = Event(), Event()
    connections: set[int] = set()

    def before_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        if conn.info.get("race_role") == "competitor" and statement.startswith(
            "UPDATE media_files"
        ):
            competitor_attempted_write.set()

    def after_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-untyped-def]
        target = (
            "INSERT INTO content_group_members" if existing_group else "INSERT INTO content_groups"
        )
        if conn.info.get("race_role") == "writer" and statement.startswith(target):
            writer_holds_lock.set()
            assert competitor_attempted_write.wait(5), "competing session did not reach its write"

    event.listen(engine, "before_cursor_execute", before_execute)
    event.listen(engine, "after_cursor_execute", after_execute)

    def confirm(role: str) -> str:
        with factory() as session:
            connection = session.connection()
            connection.info["race_role"] = role
            connections.add(id(connection.connection.driver_connection))
            repo = SqlAlchemyIdentityRepository(session)
            group = repo.confirm(left, right)
            assert repo.confirm(left, middle) == group
            session.commit()
            return group

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            writer = executor.submit(confirm, "writer")
            assert writer_holds_lock.wait(5), "writer did not reach group/membership insert"
            competitor = executor.submit(confirm, "competitor")
            assert writer.result(timeout=10) == competitor.result(timeout=10)
        assert len(connections) == 2
        with factory() as session:
            assert session.scalar(select(func.count()).select_from(ContentGroupRecord)) == 1
            members = session.scalars(select(ContentGroupMemberRecord.evidence_id)).all()
            assert set(members) == {left.id, middle.id, right.id}
            assert len(members) == 3
        assert service.confirm_duplicates(a.id, c.id) == writer.result()
    finally:
        engine.dispose()


@pytest.mark.parametrize("change", ["physical", "source", "policy"])
def test_cached_full_inspection_rechecks_binding_before_return(
    persistence_engine: Engine, change: str
) -> None:
    factory = _factory(persistence_engine)
    left, _ = _seed_pair(factory)
    gateway = _Gateway()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda _: "same"
    )
    assert service.inspect(left.id, full=True) is not None
    opened = 0

    def racing_factory() -> SqlAlchemyScanUnitOfWork:
        nonlocal opened
        opened += 1
        if opened == 2:
            if change == "policy":
                gateway.version += 1
            else:
                with factory() as session:
                    if change == "source":
                        session.execute(update(MediaSourceRecord).values(revision=99))
                    else:
                        session.execute(
                            update(MediaFileRecord)
                            .where(MediaFileRecord.id == left.id.value)
                            .values(modified_time_ns=11)
                        )
                    session.commit()
        return SqlAlchemyScanUnitOfWork(factory)

    service = IdentityCoordinator(racing_factory, gateway, lambda _: "same")
    with pytest.raises(StaleIdentityError):
        service.inspect(left.id, full=True)
    assert gateway.calls == 1


def test_explicit_confirmation_rechecks_policy_after_cached_inspections(
    persistence_engine: Engine,
) -> None:
    factory = _factory(persistence_engine)
    left, right = _seed_pair(factory)
    gateway = _Gateway()
    service = IdentityCoordinator(
        lambda: SqlAlchemyScanUnitOfWork(factory), gateway, lambda _: "same"
    )
    service.inspect(left.id, full=True)
    service.inspect(right.id, full=True)
    opened = 0

    def racing_factory() -> SqlAlchemyScanUnitOfWork:
        nonlocal opened
        opened += 1
        if opened == 5:  # Both cached inspections finished; confirmation is about to write.
            gateway.version += 1
        return SqlAlchemyScanUnitOfWork(factory)

    service = IdentityCoordinator(racing_factory, gateway, lambda _: "same")
    with pytest.raises(StaleIdentityError, match="policy"):
        service.confirm_duplicates(left.id, right.id)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ContentGroupRecord)) == 0


def test_protected_cycle_is_atomic_while_independent_rename_progresses(
    persistence_engine: Engine,
) -> None:
    from nostalgiabox.application.identity import reconcile_completed_scan
    from nostalgiabox.persistence.models import CatalogueItemRecord, PlayableRenditionRecord
    from tests.integration.test_scan_coordinator import _START

    factory = _factory(persistence_engine)
    originals = _seed_three(factory)
    old = tuple(replace(file, inode_id=index + 10) for index, file in enumerate(originals))
    fresh = tuple(
        replace(
            file,
            id=MediaFileId(f"fresh-{index}"),
            normalized_relative_locator=locator,
            original_relative_locator=locator,
            last_seen_generation=2,
        )
        for index, (file, locator) in enumerate(zip(old, ("b.mkv", "a.mkv", "d.mkv"), strict=True))
    )
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        for file in old:
            uow.inventory.store(
                replace(file, presence=FilePresenceState.MISSING, missing_since_utc=_START)
            )
        for file in fresh:
            uow.inventory.store(file)
        uow.commit()
    with factory() as session:
        session.add(CatalogueItemRecord(id="protected-item"))
        session.flush()
        session.add(
            PlayableRenditionRecord(
                id="protected-rendition",
                catalogue_item_id="protected-item",
                media_file_id=fresh[0].id.value,
                segment_start_us=0,
                segment_duration_us=1,
                logical_playable_duration_us=1,
                is_whole_file=True,
                preferred=True,
            )
        )
        session.commit()
    with SqlAlchemyScanUnitOfWork(factory) as uow:
        attention = reconcile_completed_scan(uow.identities, old[0].source_id, 2, _START)
        assert {file.id for file in attention} == {fresh[0].id, fresh[1].id}
        uow.commit()
    with factory() as session:
        repo = SqlAlchemyIdentityRepository(session)
        for file in fresh[:2]:
            assert repo.get_file(file.id) == file
        for file in old[:2]:
            current = repo.get_file(file.id)
            assert current is not None and current.presence is FilePresenceState.MISSING
            assert current.normalized_relative_locator == file.normalized_relative_locator
        moved = repo.get_file(old[2].id)
        assert moved is not None and moved.normalized_relative_locator == "d.mkv"
        assert moved.presence is FilePresenceState.PRESENT
        assert repo.get_file(fresh[2].id) is None
