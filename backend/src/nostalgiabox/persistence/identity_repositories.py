"""Append-only identity evidence and compare-and-swap physical observations."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import SQLColumnExpression, exists, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from nostalgiabox.application.identity import StaleIdentityError
from nostalgiabox.domain.catalogue import FilePresenceState, MediaFile, MediaFileId, MediaSourceId
from nostalgiabox.domain.identity import (
    DuplicateReview,
    FingerprintEvidence,
    FingerprintResult,
    IdentityEvidenceKind,
    confirms_duplicate,
    inode_continuity,
    observation_snapshot,
    snapshot,
)
from nostalgiabox.persistence.catalogue_mappers import media_file_from_record
from nostalgiabox.persistence.codecs import datetime_to_epoch_microseconds
from nostalgiabox.persistence.models import (
    ContentFingerprintRecord,
    ContentGroupMemberRecord,
    ContentGroupRecord,
    DuplicateCandidateRecord,
    IdentityDiscoveryRecord,
    IdentityDiscoveryResolutionRecord,
    IdentityRetirementRecord,
    IdentityTransitionRecord,
    MediaFileRecord,
    MediaSourceRecord,
    PlayableRenditionRecord,
    ScanRunRecord,
)


class SqlAlchemyIdentityRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_file(self, file_id: MediaFileId) -> MediaFile | None:
        row = self._session.scalar(
            select(MediaFileRecord)
            .where(
                MediaFileRecord.id == file_id.value,
                active_identity(),
            )
            .execution_options(populate_existing=True)
        )
        return None if row is None else media_file_from_record(row)

    def source_revision(self, file: MediaFile) -> int | None:
        return self._session.scalar(
            select(MediaSourceRecord.revision).where(MediaSourceRecord.id == file.source_id.value)
        )

    def binding(self, file: MediaFile) -> str:
        revision = self.source_revision(file)
        if revision is None:
            raise StaleIdentityError("source no longer exists")
        return snapshot(file, revision)

    def guard(self, expected: MediaFile) -> bool:
        """Acquire the write lock only if every discovery field still matches."""
        result = self._session.execute(
            update(MediaFileRecord)
            .where(
                MediaFileRecord.id == expected.id.value,
                MediaFileRecord.revision == expected.revision,
                active_identity(),
                MediaFileRecord.source_id == expected.source_id.value,
                MediaFileRecord.normalized_relative_locator == expected.normalized_relative_locator,
                MediaFileRecord.original_relative_locator == expected.original_relative_locator,
                MediaFileRecord.presence == expected.presence.value,
                MediaFileRecord.size_bytes == expected.size_bytes,
                MediaFileRecord.modified_time_ns == expected.modified_time_ns,
                MediaFileRecord.device_id == expected.device_id,
                MediaFileRecord.inode_id == expected.inode_id,
            )
            .values(id=expected.id.value)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    def evidence(
        self,
        file: MediaFile,
        kind: IdentityEvidenceKind,
        algorithm: str,
        version: int,
    ) -> FingerprintEvidence | None:
        current = self.get_file(file.id)
        if (
            current is None
            or current.presence is not FilePresenceState.PRESENT
            or self.binding(current) != self.binding(file)
        ):
            return None
        row = self._session.scalar(
            select(ContentFingerprintRecord)
            .where(
                ContentFingerprintRecord.media_file_id == file.id.value,
                ContentFingerprintRecord.snapshot == self.binding(file),
                ContentFingerprintRecord.kind == kind.value,
                ContentFingerprintRecord.version == version,
                ContentFingerprintRecord.algorithm == algorithm,
            )
            .order_by(ContentFingerprintRecord.id)
            .limit(1)
        )
        return None if row is None else _evidence(row)

    def historical_evidence(self, file: MediaFile) -> tuple[FingerprintEvidence, ...]:
        """Historical hashes can only veto continuity or request review, never confirm it."""
        return tuple(
            _evidence(row)
            for row in self._session.scalars(
                select(ContentFingerprintRecord)
                .where(ContentFingerprintRecord.media_file_id == file.id.value)
                .order_by(ContentFingerprintRecord.id)
            )
        )

    def historical_evidence_for_files(
        self, files: tuple[MediaFile, ...]
    ) -> dict[str, tuple[FingerprintEvidence, ...]]:
        """Load relevant immutable history in bounded queries, keyed by media-file ID."""
        history: dict[str, list[FingerprintEvidence]] = {file.id.value: [] for file in files}
        file_ids = tuple(history)
        # Keep the query parameter count comfortably below backend limits while
        # maintaining bounded (rather than per-file) database work.
        for start in range(0, len(file_ids), 500):
            rows = self._session.scalars(
                select(ContentFingerprintRecord)
                .where(ContentFingerprintRecord.media_file_id.in_(file_ids[start : start + 500]))
                .order_by(ContentFingerprintRecord.id)
            )
            for row in rows:
                history[row.media_file_id].append(_evidence(row))
        return {file_id: tuple(evidence) for file_id, evidence in history.items()}

    def add_evidence(self, evidence: FingerprintEvidence) -> None:
        file = self.get_file(MediaFileId(evidence.media_file_id))
        if (
            file is None
            or file.presence is not FilePresenceState.PRESENT
            or not self.guard(file)
            or self.binding(file) != evidence.snapshot
            or file.size_bytes != evidence.result.size_bytes
        ):
            raise StaleIdentityError("cannot append stale fingerprint")
        result = evidence.result
        self._session.add(
            ContentFingerprintRecord(
                id=evidence.id,
                media_file_id=evidence.media_file_id,
                snapshot=evidence.snapshot,
                kind=result.kind.value,
                algorithm=result.algorithm,
                version=result.version,
                digest=result.digest,
                size_bytes=result.size_bytes,
            )
        )
        self._session.flush()

    def candidates(self, evidence: FingerprintEvidence) -> tuple[FingerprintEvidence, ...]:
        result = evidence.result
        rows = self._session.scalars(
            select(ContentFingerprintRecord)
            .where(
                ContentFingerprintRecord.algorithm == result.algorithm,
                ContentFingerprintRecord.version == result.version,
                ContentFingerprintRecord.digest == result.digest,
                ContentFingerprintRecord.size_bytes == result.size_bytes,
                ContentFingerprintRecord.media_file_id != evidence.media_file_id,
            )
            .order_by(ContentFingerprintRecord.id)
        ).all()
        current: list[FingerprintEvidence] = []
        for row in rows:
            file = self.get_file(MediaFileId(row.media_file_id))
            if file is not None and self.binding(file) == row.snapshot:
                current.append(_evidence(row))
        return tuple(current)

    def add_candidate(self, left: FingerprintEvidence, right: FingerprintEvidence) -> None:
        if (
            left.media_file_id == right.media_file_id
            or left.result.content_key != right.result.content_key
        ):
            raise ValueError("candidate requires distinct files and matching evidence")
        for evidence in (left, right):
            row = self._session.get(ContentFingerprintRecord, evidence.id)
            file = self.get_file(MediaFileId(evidence.media_file_id))
            if (
                row is None
                or _evidence(row) != evidence
                or file is None
                or not self.guard(file)
                or self.binding(file) != evidence.snapshot
            ):
                raise StaleIdentityError("candidate evidence is stale")
        a, b = sorted((left.id, right.id))
        existing = self._session.scalar(
            select(DuplicateCandidateRecord.id).where(
                DuplicateCandidateRecord.left_evidence_id == a,
                DuplicateCandidateRecord.right_evidence_id == b,
            )
        )
        if existing is None:
            self._session.add(
                DuplicateCandidateRecord(
                    id=str(uuid4()),
                    left_evidence_id=a,
                    right_evidence_id=b,
                    reason="file.possible_duplicate",
                )
            )
            self._session.flush()

    def reviews(self, file_id: MediaFileId) -> tuple[DuplicateReview, ...]:
        evidence_ids = select(ContentFingerprintRecord.id).where(
            ContentFingerprintRecord.media_file_id == file_id.value
        )
        rows = self._session.scalars(
            select(DuplicateCandidateRecord)
            .where(
                DuplicateCandidateRecord.left_evidence_id.in_(evidence_ids)
                | DuplicateCandidateRecord.right_evidence_id.in_(evidence_ids)
            )
            .order_by(DuplicateCandidateRecord.id)
        ).all()
        reviews: list[DuplicateReview] = []
        for row in rows:
            left_row = self._session.get(ContentFingerprintRecord, row.left_evidence_id)
            right_row = self._session.get(ContentFingerprintRecord, row.right_evidence_id)
            assert left_row is not None and right_row is not None
            left, right = _evidence(left_row), _evidence(right_row)
            current = all(
                (file := self.get_file(MediaFileId(e.media_file_id))) is not None
                and self.binding(file) == e.snapshot
                for e in (left, right)
            )
            # Quick candidates may be confirmed later using separate full evidence.
            groups: list[set[str]] = []
            for evidence in (left, right):
                groups.append(
                    set(
                        self._session.scalars(
                            select(ContentGroupMemberRecord.group_id)
                            .join(
                                ContentFingerprintRecord,
                                ContentFingerprintRecord.id == ContentGroupMemberRecord.evidence_id,
                            )
                            .where(
                                ContentFingerprintRecord.media_file_id == evidence.media_file_id,
                                ContentFingerprintRecord.snapshot == evidence.snapshot,
                            )
                        ).all()
                    )
                )
            common = sorted(groups[0] & groups[1])
            reviews.append(
                DuplicateReview(row.id, left, right, current, common[0] if common else None)
            )
        return tuple(reviews)

    def confirmed_group(self, left: FingerprintEvidence, right: FingerprintEvidence) -> str | None:
        if left.media_file_id == right.media_file_id or not confirms_duplicate(
            left.result, right.result
        ):
            return None
        groups = self._session.scalars(
            select(ContentGroupMemberRecord.group_id)
            .where(ContentGroupMemberRecord.evidence_id == left.id)
            .intersect(
                select(ContentGroupMemberRecord.group_id).where(
                    ContentGroupMemberRecord.evidence_id == right.id
                )
            )
        ).all()
        return min(groups) if groups else None

    def confirm(self, left: FingerprintEvidence, right: FingerprintEvidence) -> str:
        if left.media_file_id == right.media_file_id or not confirms_duplicate(
            left.result, right.result
        ):
            raise ValueError("only full SHA-256 can confirm distinct locations")
        for evidence in (left, right):
            row = self._session.get(ContentFingerprintRecord, evidence.id)
            file = self.get_file(MediaFileId(evidence.media_file_id))
            if (
                row is None
                or _evidence(row) != evidence
                or file is None
                or file.presence is not FilePresenceState.PRESENT
                or not self.guard(file)
                or self.binding(file) != evidence.snapshot
            ):
                raise StaleIdentityError("confirmation requires current persisted evidence")
        result = left.result
        group = self._content_group(result)
        for evidence in (left, right):
            if self._has_group_member(group.id, evidence.id):
                continue
            try:
                # A SAVEPOINT contains a competing member insert without poisoning
                # the caller's UoW. It also makes repeated confirms in one UoW safe
                # when autoflush is deliberately disabled.
                with self._session.begin_nested():
                    self._session.add(
                        ContentGroupMemberRecord(group_id=group.id, evidence_id=evidence.id)
                    )
                    self._session.flush()
            except IntegrityError:
                if not self._has_group_member(group.id, evidence.id):
                    raise
        return group.id

    def _content_group(self, result: FingerprintResult) -> ContentGroupRecord:
        for pending in self._session.new:
            if (
                isinstance(pending, ContentGroupRecord)
                and (
                    pending.algorithm,
                    pending.version,
                    pending.digest,
                    pending.size_bytes,
                )
                == result.content_key
            ):
                return pending
        group = self._session.scalar(
            select(ContentGroupRecord).where(
                ContentGroupRecord.algorithm == result.algorithm,
                ContentGroupRecord.version == result.version,
                ContentGroupRecord.digest == result.digest,
                ContentGroupRecord.size_bytes == result.size_bytes,
            )
        )
        if group is not None:
            return group
        group = ContentGroupRecord(
            id=str(uuid4()),
            algorithm=result.algorithm,
            version=result.version,
            digest=result.digest,
            size_bytes=result.size_bytes,
        )
        try:
            with self._session.begin_nested():
                self._session.add(group)
                self._session.flush()
        except IntegrityError:
            group = self._session.scalar(
                select(ContentGroupRecord).where(
                    ContentGroupRecord.algorithm == result.algorithm,
                    ContentGroupRecord.version == result.version,
                    ContentGroupRecord.digest == result.digest,
                    ContentGroupRecord.size_bytes == result.size_bytes,
                )
            )
            if group is None:
                raise
        return group

    def _has_group_member(self, group_id: str, evidence_id: str) -> bool:
        return (
            any(
                isinstance(pending, ContentGroupMemberRecord)
                and pending.group_id == group_id
                and pending.evidence_id == evidence_id
                for pending in self._session.new
            )
            or self._session.get(ContentGroupMemberRecord, (group_id, evidence_id)) is not None
        )

    def reconciliation_files(self, source_id: MediaSourceId) -> tuple[MediaFile, ...]:
        """Return active rows except terminal failed-run provisional discoveries.

        Resolution records are immutable lifecycle evidence. Once present,
        their discovery row cannot participate in any later reconciliation
        graph, even if the physical row subsequently becomes missing.
        """
        rows = self._session.scalars(
            select(MediaFileRecord)
            .outerjoin(
                IdentityDiscoveryResolutionRecord,
                IdentityDiscoveryResolutionRecord.media_file_id == MediaFileRecord.id,
            )
            .where(
                MediaFileRecord.source_id == source_id.value,
                active_identity(),
                IdentityDiscoveryResolutionRecord.media_file_id.is_(None),
            )
            .order_by(MediaFileRecord.id)
            .execution_options(populate_existing=True)
        ).all()
        return tuple(media_file_from_record(row) for row in rows)

    def discoveries(self, source_id: MediaSourceId, generation: int) -> tuple[str, ...]:
        """Select only rows observed by this authoritative completion.

        Failed/cancelled/interrupted scans leave their first-generation rows
        provisional. A later completed scan may reconsider one only after it
        observes that same active row. Completed-origin rows stay generation-local.
        """
        return tuple(
            self._session.scalars(
                select(IdentityDiscoveryRecord.media_file_id)
                .join(
                    MediaFileRecord,
                    MediaFileRecord.id == IdentityDiscoveryRecord.media_file_id,
                )
                .outerjoin(
                    ScanRunRecord,
                    (ScanRunRecord.source_id == MediaFileRecord.source_id)
                    & (ScanRunRecord.generation == IdentityDiscoveryRecord.generation),
                )
                .outerjoin(
                    IdentityDiscoveryResolutionRecord,
                    IdentityDiscoveryResolutionRecord.media_file_id
                    == IdentityDiscoveryRecord.media_file_id,
                )
                .where(
                    MediaFileRecord.source_id == source_id.value,
                    MediaFileRecord.presence == FilePresenceState.PRESENT.value,
                    MediaFileRecord.last_seen_generation == generation,
                    (
                        (IdentityDiscoveryRecord.generation == generation)
                        | (
                            ScanRunRecord.status.in_(("cancelled", "interrupted", "failed"))
                            & IdentityDiscoveryResolutionRecord.media_file_id.is_(None)
                        )
                    ),
                )
                .order_by(IdentityDiscoveryRecord.media_file_id)
            ).all()
        )

    def finalize_provisionals(self, source_id: MediaSourceId, generation: int) -> None:
        """Seal every pending failed-run discovery after an authoritative scan."""
        rows = self._session.execute(
            select(
                IdentityDiscoveryRecord.media_file_id,
                MediaFileRecord.presence,
                MediaFileRecord.last_seen_generation,
            )
            .join(MediaFileRecord, MediaFileRecord.id == IdentityDiscoveryRecord.media_file_id)
            .join(
                ScanRunRecord,
                (ScanRunRecord.source_id == MediaFileRecord.source_id)
                & (ScanRunRecord.generation == IdentityDiscoveryRecord.generation),
            )
            .outerjoin(
                IdentityDiscoveryResolutionRecord,
                IdentityDiscoveryResolutionRecord.media_file_id
                == IdentityDiscoveryRecord.media_file_id,
            )
            .where(
                MediaFileRecord.source_id == source_id.value,
                ScanRunRecord.status.in_(("cancelled", "interrupted", "failed")),
                IdentityDiscoveryResolutionRecord.media_file_id.is_(None),
            )
        ).all()
        for file_id, presence, last_seen_generation in rows:
            lifecycle = (
                "resolved"
                if (
                    presence == FilePresenceState.PRESENT.value
                    and last_seen_generation == generation
                )
                else "stale"
            )
            self._session.add(
                IdentityDiscoveryResolutionRecord(
                    media_file_id=file_id,
                    lifecycle=lifecycle,
                    authoritative_generation=generation,
                )
            )

    def transition(
        self,
        old: MediaFile,
        new: MediaFile,
        kind: str,
        reason: str,
        at: datetime,
        *,
        retire: MediaFile | None = None,
    ) -> None:
        if not self.guard(old) or not self.guard(new):
            raise StaleIdentityError("transition observation is stale")
        predecessor_snapshot = observation_snapshot(old)
        successor_snapshot = observation_snapshot(new)
        existing = self._session.scalar(
            select(IdentityTransitionRecord.id).where(
                IdentityTransitionRecord.kind == kind,
                IdentityTransitionRecord.predecessor_id == old.id.value,
                IdentityTransitionRecord.successor_id == new.id.value,
                IdentityTransitionRecord.predecessor_snapshot == predecessor_snapshot,
                IdentityTransitionRecord.successor_snapshot == successor_snapshot,
                IdentityTransitionRecord.reason == reason,
            )
        )
        if existing is not None:
            return
        transition_id = str(uuid4())
        self._session.add(
            IdentityTransitionRecord(
                id=transition_id,
                kind=kind,
                predecessor_id=old.id.value,
                successor_id=new.id.value,
                predecessor_snapshot=predecessor_snapshot,
                successor_snapshot=successor_snapshot,
                reason=reason,
                occurred_utc_us=datetime_to_epoch_microseconds(at),
            )
        )
        self._session.flush()
        if retire is not None:
            if not self.guard(retire):
                raise StaleIdentityError("retirement observation is stale")
            self._session.execute(
                update(MediaFileRecord)
                .where(
                    MediaFileRecord.id == retire.id.value,
                )
                .values(presence="missing", missing_since_utc_us=datetime_to_epoch_microseconds(at))
            )
            self._session.add(
                IdentityRetirementRecord(
                    media_file_id=retire.id.value,
                    transition_id=transition_id,
                )
            )
            self._session.flush()

    def move_many(
        self, pairs: tuple[tuple[MediaFile, MediaFile], ...], at: datetime
    ) -> tuple[MediaFile, ...]:
        if not pairs:
            return ()
        source = self._session.get(MediaSourceRecord, pairs[0][0].source_id.value)
        if source is None or source.kind != "local":
            raise ValueError("rename requires a local source")
        old_ids = {old.id.value for old, _ in pairs}
        new_ids = {new.id.value for _, new in pairs}
        if len(old_ids) != len(pairs) or len(new_ids) != len(pairs):
            raise ValueError("rename graph must be one-to-one")
        for old, provisional in pairs:
            if (
                not inode_continuity(old, provisional)
                or old.source_id.value != source.id
                or old.presence is not FilePresenceState.MISSING
                or provisional.presence is not FilePresenceState.PRESENT
                or old.id == provisional.id
                or old.normalized_relative_locator == provisional.normalized_relative_locator
                or not self.guard(old)
                or not self.guard(provisional)
            ):
                raise StaleIdentityError("rename graph observation changed")
        blocked_ids = set(
            self._session.scalars(
                select(PlayableRenditionRecord.media_file_id).where(
                    PlayableRenditionRecord.media_file_id.in_(new_ids)
                )
            ).all()
        )
        blocked = tuple(new for _, new in pairs if new.id.value in blocked_ids)
        if blocked:
            return blocked
        # Retire every provisional row before restoring any established ID.
        for old, provisional in pairs:
            self.transition(
                old, provisional, "confident_rename", "unique_local_inode", at, retire=provisional
            )
        for old, provisional in pairs:
            self._session.execute(
                update(MediaFileRecord)
                .where(MediaFileRecord.id == old.id.value)
                .values(
                    normalized_relative_locator=provisional.normalized_relative_locator,
                    original_relative_locator=provisional.original_relative_locator,
                    presence="present",
                    missing_since_utc_us=None,
                    last_seen_generation=provisional.last_seen_generation,
                    last_observed_utc_us=datetime_to_epoch_microseconds(at),
                    probe_state="discovered",
                    probe_observation_signature=None,
                    probe_capability_version=None,
                )
            )
        return ()


def active_identity() -> SQLColumnExpression[bool]:
    return ~exists().where(IdentityRetirementRecord.media_file_id == MediaFileRecord.id)


def _evidence(row: ContentFingerprintRecord) -> FingerprintEvidence:
    return FingerprintEvidence(
        row.id,
        row.media_file_id,
        row.snapshot,
        FingerprintResult(
            IdentityEvidenceKind(row.kind), row.algorithm, row.version, row.digest, row.size_bytes
        ),
    )
