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
    with op.batch_alter_table("media_files") as batch:
        batch.add_column(
            sa.Column("probe_state", sa.String(), nullable=False, server_default="discovered")
        )
        batch.add_column(sa.Column("probe_observation_signature", sa.String(), nullable=True))
        batch.add_column(sa.Column("probe_capability_version", sa.String(), nullable=True))
        batch.create_check_constraint(
            "ck_media_files_probe_state",
            "probe_state IN ('discovered', 'inspected', 'compatible_candidate', 'unsupported', 'inspection_failed')",
        )
        batch.create_check_constraint(
            "ck_media_files_probe_evidence",
            "(probe_state = 'discovered' AND probe_observation_signature IS NULL AND probe_capability_version IS NULL) OR (probe_state != 'discovered' AND length(trim(probe_observation_signature)) > 0 AND length(trim(probe_capability_version)) > 0)",
        )
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
    with op.batch_alter_table("media_files") as batch:
        batch.drop_constraint("ck_media_files_probe_evidence", type_="check")
        batch.drop_constraint("ck_media_files_probe_state", type_="check")
        batch.drop_column("probe_capability_version")
        batch.drop_column("probe_observation_signature")
        batch.drop_column("probe_state")
