"""Add immutable physical identity evidence after Task 3.4.

Revision ID: 20260915_0006
Revises: 20260914_0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260915_0006"
down_revision: str | Sequence[str] | None = "20260914_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "identity_transitions",
    "identity_retirements",
    "content_fingerprints",
    "content_groups",
    "content_group_members",
    "duplicate_candidates",
    "identity_discoveries",
    "identity_discovery_resolutions",
)


def _file(name: str, *, primary: bool = False) -> sa.Column[str]:
    return sa.Column(
        name,
        sa.String(),
        sa.ForeignKey("media_files.id", ondelete="RESTRICT"),
        primary_key=primary,
        nullable=False,
    )


def _text(name: str) -> sa.Column[str]:
    return sa.Column(name, sa.String(), nullable=False)


def upgrade() -> None:
    op.add_column(
        "media_files", sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
    )
    op.execute(
        "CREATE TRIGGER media_files_identity_revision AFTER UPDATE ON media_files WHEN "
        "OLD.source_id IS NOT NEW.source_id OR "
        "OLD.normalized_relative_locator IS NOT NEW.normalized_relative_locator OR "
        "OLD.original_relative_locator IS NOT NEW.original_relative_locator OR "
        "OLD.presence IS NOT NEW.presence OR "
        "OLD.size_bytes IS NOT NEW.size_bytes OR "
        "OLD.modified_time_ns IS NOT NEW.modified_time_ns OR "
        "OLD.device_id IS NOT NEW.device_id OR "
        "OLD.inode_id IS NOT NEW.inode_id BEGIN "
        "UPDATE media_files SET revision = OLD.revision + 1 WHERE id = NEW.id; END"
    )
    op.create_table(
        "identity_transitions",
        sa.Column("id", sa.String(), primary_key=True),
        _text("kind"),
        _file("predecessor_id"),
        _file("successor_id"),
        _text("predecessor_snapshot"),
        _text("successor_snapshot"),
        _text("reason"),
        sa.Column("occurred_utc_us", sa.Integer(), nullable=False),
        sa.CheckConstraint("kind IN ('replacement', 'confident_rename', 'needs_attention')"),
        sa.CheckConstraint("predecessor_id != successor_id"),
        sa.UniqueConstraint(
            "kind",
            "predecessor_id",
            "successor_id",
            "predecessor_snapshot",
            "successor_snapshot",
            "reason",
            name="uq_identity_transition_decision",
        ),
    )
    op.create_index(
        "ix_identity_transitions_predecessor", "identity_transitions", ["predecessor_id"]
    )
    op.create_index("ix_identity_transitions_successor", "identity_transitions", ["successor_id"])
    op.create_table(
        "identity_retirements",
        _file("media_file_id", primary=True),
        sa.Column(
            "transition_id",
            sa.String(),
            sa.ForeignKey("identity_transitions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
    )
    op.create_table(
        "content_fingerprints",
        sa.Column("id", sa.String(), primary_key=True),
        _file("media_file_id"),
        _text("snapshot"),
        _text("kind"),
        _text("algorithm"),
        sa.Column("version", sa.Integer(), nullable=False),
        _text("digest"),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "version > 0 AND size_bytes >= 0 AND length(digest) = 64 "
            "AND digest NOT GLOB '*[^0-9a-f]*'"
        ),
        sa.CheckConstraint(
            "(kind = 'quick' AND algorithm = 'sha256-sampled') OR "
            "(kind = 'full_sha256' AND algorithm = 'sha256')"
        ),
    )
    op.create_index(
        "ix_fingerprint_candidates",
        "content_fingerprints",
        ["algorithm", "version", "digest", "size_bytes"],
    )
    op.create_index(
        "ix_fingerprint_observation", "content_fingerprints", ["media_file_id", "snapshot"]
    )
    op.create_table(
        "content_groups",
        sa.Column("id", sa.String(), primary_key=True),
        _text("algorithm"),
        sa.Column("version", sa.Integer(), nullable=False),
        _text("digest"),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "algorithm = 'sha256' AND version > 0 AND size_bytes >= 0 AND length(digest) = 64 "
            "AND digest NOT GLOB '*[^0-9a-f]*'"
        ),
        sa.UniqueConstraint("algorithm", "version", "digest", "size_bytes"),
    )
    op.create_table(
        "content_group_members",
        sa.Column(
            "group_id",
            sa.String(),
            sa.ForeignKey("content_groups.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "evidence_id",
            sa.String(),
            sa.ForeignKey("content_fingerprints.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
    )
    op.create_table(
        "duplicate_candidates",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "left_evidence_id",
            sa.String(),
            sa.ForeignKey("content_fingerprints.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "right_evidence_id",
            sa.String(),
            sa.ForeignKey("content_fingerprints.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        _text("reason"),
        sa.UniqueConstraint("left_evidence_id", "right_evidence_id"),
        sa.CheckConstraint("left_evidence_id < right_evidence_id"),
    )
    op.create_table(
        "identity_discoveries",
        _file("media_file_id", primary=True),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.CheckConstraint("generation > 0"),
    )
    op.create_table(
        "identity_discovery_resolutions",
        sa.Column(
            "media_file_id",
            sa.String(),
            sa.ForeignKey("identity_discoveries.media_file_id", ondelete="RESTRICT"),
            primary_key=True,
            nullable=False,
        ),
        _text("lifecycle"),
        sa.Column("authoritative_generation", sa.Integer(), nullable=False),
        sa.CheckConstraint("lifecycle IN ('resolved', 'stale')"),
        sa.CheckConstraint("authoritative_generation > 0"),
    )
    # SQLite is the accepted database. Application repositories expose append-only
    # operations; triggers additionally prevent accidental raw evidence rewrites.
    for table in _TABLES:
        for operation in ("UPDATE", "DELETE"):
            op.execute(
                f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'identity evidence is immutable'); END"
            )
    op.execute("""CREATE TRIGGER content_group_members_full_only
        BEFORE INSERT ON content_group_members
        WHEN NOT EXISTS (SELECT 1 FROM content_fingerprints f JOIN content_groups g
            ON g.id = NEW.group_id WHERE f.id = NEW.evidence_id AND f.kind = 'full_sha256'
            AND f.algorithm = g.algorithm AND f.version = g.version
            AND f.digest = g.digest AND f.size_bytes = g.size_bytes)
        BEGIN SELECT RAISE(ABORT, 'full content identity required'); END""")


def downgrade() -> None:
    op.execute("DROP TRIGGER media_files_identity_revision")
    op.drop_column("media_files", "revision")
    for table in reversed(_TABLES):
        op.drop_table(table)
