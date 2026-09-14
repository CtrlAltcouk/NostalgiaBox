"""Add versioned ffprobe inspection state without changing discovery history.

Revision ID: 20260914_0005
Revises: 20260810_0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260914_0005"
down_revision: str | Sequence[str] | None = "20260810_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite cannot batch-rebuild media_files while existing Phase 3 tables
    # reference it with foreign_keys enabled. These additive columns are safe
    # with direct ALTER TABLE and domain/ORM validation enforces their pairing.
    op.add_column(
        "media_files",
        sa.Column("probe_state", sa.String(), nullable=False, server_default="discovered"),
    )
    op.add_column(
        "media_files", sa.Column("probe_observation_signature", sa.String(), nullable=True)
    )
    op.add_column("media_files", sa.Column("probe_capability_version", sa.String(), nullable=True))
    op.create_table(
        "probe_attempts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "media_file_id",
            sa.String(),
            sa.ForeignKey("media_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("observation_signature", sa.String(), nullable=False),
        sa.Column("capability_version", sa.String(), nullable=False),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("attempted_utc_us", sa.Integer(), nullable=False),
        sa.Column("failure_code", sa.String(), nullable=True),
        sa.Column("failure_message", sa.String(), nullable=True),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_probe_attempts_id_nonblank"),
        sa.CheckConstraint(
            "length(trim(observation_signature)) > 0", name="ck_probe_attempts_signature_nonblank"
        ),
        sa.CheckConstraint(
            "length(trim(capability_version)) > 0", name="ck_probe_attempts_capability_nonblank"
        ),
        sa.CheckConstraint(
            "state IN ('compatible_candidate', 'unsupported', 'inspection_failed')",
            name="ck_probe_attempts_state",
        ),
        sa.CheckConstraint(
            "(state = 'inspection_failed') = (failure_code IS NOT NULL)",
            name="ck_probe_attempts_failure_code",
        ),
        sa.CheckConstraint(
            "(failure_code IS NULL) = (failure_message IS NULL)",
            name="ck_probe_attempts_failure_pair",
        ),
    )
    op.create_index(
        "ix_probe_attempts_file_attempted", "probe_attempts", ["media_file_id", "attempted_utc_us"]
    )
    op.create_table(
        "probe_observations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "media_file_id",
            sa.String(),
            sa.ForeignKey("media_files.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("observation_signature", sa.String(), nullable=False),
        sa.Column("capability_version", sa.String(), nullable=False),
        sa.Column("duration_us", sa.Integer(), nullable=False),
        sa.Column("containers_json", sa.String(), nullable=False),
        sa.Column("streams_json", sa.String(), nullable=False),
        sa.Column("compatible_candidate", sa.Boolean(), nullable=False),
        sa.Column("inspected_utc_us", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_probe_observations_id_nonblank"),
        sa.CheckConstraint(
            "length(trim(observation_signature)) > 0",
            name="ck_probe_observations_signature_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(capability_version)) > 0", name="ck_probe_observations_capability_nonblank"
        ),
        sa.CheckConstraint("duration_us >= 0", name="ck_probe_observations_duration_nonnegative"),
    )
    op.create_index(
        "ix_probe_observations_file_signature_capability",
        "probe_observations",
        ["media_file_id", "observation_signature", "capability_version"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_probe_observations_file_signature_capability", table_name="probe_observations"
    )
    op.drop_table("probe_observations")
    op.drop_index("ix_probe_attempts_file_attempted", table_name="probe_attempts")
    op.drop_table("probe_attempts")
    op.drop_column("media_files", "probe_capability_version")
    op.drop_column("media_files", "probe_observation_signature")
    op.drop_column("media_files", "probe_state")
