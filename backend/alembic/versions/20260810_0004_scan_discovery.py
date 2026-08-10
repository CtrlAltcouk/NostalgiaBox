"""Add durable local scan discovery state without classifying legacy files.

Revision ID: 20260810_0004
Revises: 20260810_0003
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0004"
down_revision: str | Sequence[str] | None = "20260810_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add scanner observations, durable runs/issues and partial uniqueness guards."""
    op.add_column(
        "media_files",
        sa.Column(
            "presence",
            sa.String(),
            sa.CheckConstraint(
                "presence IN ('unclassified', 'present', 'missing')",
                name="ck_media_files_presence",
            ),
            nullable=False,
            server_default="unclassified",
        ),
    )
    op.add_column(
        "media_files",
        sa.Column(
            "size_bytes",
            sa.Integer(),
            sa.CheckConstraint(
                "size_bytes IS NULL OR size_bytes >= 0",
                name="ck_media_files_size_nonnegative",
            ),
            nullable=True,
        ),
    )
    op.add_column("media_files", sa.Column("modified_time_ns", sa.Integer(), nullable=True))
    op.add_column("media_files", sa.Column("device_id", sa.Integer(), nullable=True))
    op.add_column("media_files", sa.Column("inode_id", sa.Integer(), nullable=True))
    op.add_column(
        "media_files",
        sa.Column(
            "last_seen_generation",
            sa.Integer(),
            sa.CheckConstraint(
                "last_seen_generation IS NULL OR last_seen_generation >= 1",
                name="ck_media_files_seen_generation_positive",
            ),
            nullable=True,
        ),
    )
    op.add_column("media_files", sa.Column("first_observed_utc_us", sa.Integer(), nullable=True))
    op.add_column("media_files", sa.Column("last_observed_utc_us", sa.Integer(), nullable=True))
    op.add_column(
        "media_files",
        sa.Column(
            "missing_since_utc_us",
            sa.Integer(),
            sa.CheckConstraint(
                "(presence = 'unclassified' AND size_bytes IS NULL "
                "AND modified_time_ns IS NULL AND device_id IS NULL AND inode_id IS NULL "
                "AND last_seen_generation IS NULL AND first_observed_utc_us IS NULL "
                "AND last_observed_utc_us IS NULL AND missing_since_utc_us IS NULL) OR "
                "(presence IN ('present', 'missing') AND size_bytes IS NOT NULL "
                "AND modified_time_ns IS NOT NULL AND last_seen_generation IS NOT NULL "
                "AND first_observed_utc_us IS NOT NULL AND last_observed_utc_us IS NOT NULL)",
                name="ck_media_files_observation_state",
            ),
            sa.CheckConstraint(
                "(presence = 'missing') = (missing_since_utc_us IS NOT NULL)",
                name="ck_media_files_missing_timestamp",
            ),
            nullable=True,
        ),
    )
    op.create_index("ix_media_files_source_presence", "media_files", ["source_id", "presence"])
    op.create_index(
        "ix_media_files_source_generation",
        "media_files",
        ["source_id", "last_seen_generation"],
    )
    op.create_index(
        "uq_media_files_present_source_locator",
        "media_files",
        ["source_id", "normalized_relative_locator"],
        unique=True,
        sqlite_where=sa.text("presence = 'present'"),
    )

    op.create_table(
        "scan_runs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False),
        sa.Column("queued_utc_us", sa.Integer(), nullable=False),
        sa.Column("started_utc_us", sa.Integer(), nullable=True),
        sa.Column("finished_utc_us", sa.Integer(), nullable=True),
        sa.Column("source_revision", sa.Integer(), nullable=True),
        sa.Column("source_root", sa.String(), nullable=True),
        sa.Column("discovered_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("added_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unchanged_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("changed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ignored_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("issue_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("terminal_error_code", sa.String(), nullable=True),
        sa.Column("terminal_error_message", sa.String(), nullable=True),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_scan_runs_id_nonblank"),
        sa.CheckConstraint("kind IN ('full', 'incremental')", name="ck_scan_runs_kind"),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'cancelled', 'interrupted', 'failed')",
            name="ck_scan_runs_status",
        ),
        sa.CheckConstraint("generation >= 1", name="ck_scan_runs_generation_positive"),
        sa.CheckConstraint(
            "cancellation_requested IN (0, 1)", name="ck_scan_runs_cancellation_boolean"
        ),
        sa.CheckConstraint(
            "discovered_count >= 0 AND added_count >= 0 AND unchanged_count >= 0 "
            "AND changed_count >= 0 AND missing_count >= 0 AND ignored_count >= 0 "
            "AND issue_count >= 0",
            name="ck_scan_runs_counts_nonnegative",
        ),
        sa.CheckConstraint(
            "added_count + unchanged_count + changed_count <= discovered_count",
            name="ck_scan_runs_outcomes_within_discovered",
        ),
        sa.CheckConstraint(
            "(source_revision IS NULL) = (source_root IS NULL)",
            name="ck_scan_runs_source_snapshot_pair",
        ),
        sa.CheckConstraint(
            "source_revision IS NULL OR source_revision >= 1",
            name="ck_scan_runs_source_revision_positive",
        ),
        sa.CheckConstraint(
            "source_root IS NULL OR length(trim(source_root)) > 0",
            name="ck_scan_runs_source_root_nonblank",
        ),
        sa.CheckConstraint(
            "(terminal_error_code IS NULL) = (terminal_error_message IS NULL)",
            name="ck_scan_runs_error_pair",
        ),
        sa.CheckConstraint(
            "terminal_error_code IS NULL OR length(trim(terminal_error_code)) > 0",
            name="ck_scan_runs_error_code_nonblank",
        ),
        sa.CheckConstraint(
            "terminal_error_message IS NULL OR length(trim(terminal_error_message)) > 0",
            name="ck_scan_runs_error_message_nonblank",
        ),
        sa.CheckConstraint(
            "(status = 'queued' AND started_utc_us IS NULL AND finished_utc_us IS NULL) OR "
            "(status = 'running' AND started_utc_us IS NOT NULL AND finished_utc_us IS NULL) OR "
            "(status = 'completed' AND started_utc_us IS NOT NULL "
            "AND finished_utc_us IS NOT NULL) OR "
            "(status IN ('cancelled', 'interrupted', 'failed') "
            "AND finished_utc_us IS NOT NULL)",
            name="ck_scan_runs_status_timestamps",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["media_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "generation", name="uq_scan_runs_source_generation"),
    )
    op.create_index("ix_scan_runs_source_queued", "scan_runs", ["source_id", "queued_utc_us"])
    op.create_index("ix_scan_runs_status", "scan_runs", ["status"])
    op.create_index(
        "uq_scan_runs_active_source",
        "scan_runs",
        ["source_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )

    op.create_table(
        "scan_issues",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("media_file_id", sa.String(), nullable=True),
        sa.Column("relative_locator", sa.String(), nullable=True),
        sa.Column("deduplication_key", sa.String(), nullable=False),
        sa.Column("code", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("severity", sa.String(), nullable=False),
        sa.Column("occurred_utc_us", sa.Integer(), nullable=False),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_scan_issues_id_nonblank"),
        sa.CheckConstraint(
            "length(trim(deduplication_key)) > 0", name="ck_scan_issues_key_nonblank"
        ),
        sa.CheckConstraint("length(trim(code)) > 0", name="ck_scan_issues_code_nonblank"),
        sa.CheckConstraint("length(trim(message)) > 0", name="ck_scan_issues_message_nonblank"),
        sa.CheckConstraint(
            "severity IN ('info', 'warning', 'error')", name="ck_scan_issues_severity"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["scan_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_file_id"], ["media_files.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "deduplication_key", name="uq_scan_issues_run_key"),
    )
    op.create_index("ix_scan_issues_run_occurred", "scan_issues", ["run_id", "occurred_utc_us"])
    op.create_index("ix_scan_issues_code", "scan_issues", ["code"])


def downgrade() -> None:
    """Restore the exact Task 3.2 schema and preserve its pre-scanner columns."""
    op.drop_index("ix_scan_issues_code", table_name="scan_issues")
    op.drop_index("ix_scan_issues_run_occurred", table_name="scan_issues")
    op.drop_table("scan_issues")
    op.drop_index("uq_scan_runs_active_source", table_name="scan_runs")
    op.drop_index("ix_scan_runs_status", table_name="scan_runs")
    op.drop_index("ix_scan_runs_source_queued", table_name="scan_runs")
    op.drop_table("scan_runs")
    op.drop_index("uq_media_files_present_source_locator", table_name="media_files")
    op.drop_index("ix_media_files_source_generation", table_name="media_files")
    op.drop_index("ix_media_files_source_presence", table_name="media_files")
    for column in (
        "missing_since_utc_us",
        "last_observed_utc_us",
        "first_observed_utc_us",
        "last_seen_generation",
        "inode_id",
        "device_id",
        "modified_time_ns",
        "size_bytes",
        "presence",
    ):
        op.drop_column("media_files", column)
