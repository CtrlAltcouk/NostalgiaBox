"""Add local source lifecycle and availability state.

Revision ID: 20260810_0003
Revises: 20260809_0002
Create Date: 2026-08-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260810_0003"
down_revision: str | Sequence[str] | None = "20260809_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable compatibility configuration and conservative lifecycle defaults."""
    op.add_column(
        "media_sources",
        sa.Column(
            "display_name",
            sa.String(),
            sa.CheckConstraint(
                "display_name IS NULL OR length(trim(display_name)) > 0",
                name="ck_media_sources_display_name_nonblank",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "media_sources",
        sa.Column(
            "configured_root",
            sa.String(),
            sa.CheckConstraint(
                "configured_root IS NULL OR length(trim(configured_root)) > 0",
                name="ck_media_sources_configured_root_nonblank",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "media_sources",
        sa.Column(
            "enabled",
            sa.Boolean(),
            sa.CheckConstraint("enabled IN (0, 1)", name="ck_media_sources_enabled_boolean"),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "media_sources",
        sa.Column(
            "availability",
            sa.String(),
            sa.CheckConstraint(
                "availability IN ('unknown', 'available', 'unavailable', "
                "'authentication_failed', 'permission_denied', 'invalid_root', 'error')",
                name="ck_media_sources_availability",
            ),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column("media_sources", sa.Column("last_checked_utc_us", sa.Integer(), nullable=True))
    op.add_column(
        "media_sources", sa.Column("last_successful_scan_utc_us", sa.Integer(), nullable=True)
    )
    op.add_column(
        "media_sources",
        sa.Column(
            "current_error_code",
            sa.String(),
            sa.CheckConstraint(
                "current_error_code IS NULL OR length(trim(current_error_code)) > 0",
                name="ck_media_sources_error_code_nonblank",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "media_sources",
        sa.Column(
            "current_error_message",
            sa.String(),
            sa.CheckConstraint(
                "current_error_message IS NULL OR length(trim(current_error_message)) > 0",
                name="ck_media_sources_error_message_nonblank",
            ),
            sa.CheckConstraint(
                "(current_error_code IS NULL) = (current_error_message IS NULL)",
                name="ck_media_sources_error_pair",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "media_sources",
        sa.Column(
            "retired_utc_us",
            sa.Integer(),
            sa.CheckConstraint(
                "retired_utc_us IS NULL OR enabled = 0",
                name="ck_media_sources_retired_disabled",
            ),
            nullable=True,
        ),
    )
    op.add_column(
        "media_sources",
        sa.Column(
            "revision",
            sa.Integer(),
            sa.CheckConstraint("revision >= 1", name="ck_media_sources_revision_positive"),
            nullable=False,
            server_default="1",
        ),
    )
    op.execute(sa.text("UPDATE media_sources SET display_name = id WHERE display_name IS NULL"))
    op.create_index(
        "ix_media_sources_enabled_availability",
        "media_sources",
        ["enabled", "availability"],
    )


def downgrade() -> None:
    """Remove only Task 3.2 source lifecycle columns and restore Task 3.1 shape."""
    op.drop_index("ix_media_sources_enabled_availability", table_name="media_sources")
    for column in (
        "revision",
        "retired_utc_us",
        "current_error_message",
        "current_error_code",
        "last_successful_scan_utc_us",
        "last_checked_utc_us",
        "availability",
        "enabled",
        "configured_root",
        "display_name",
    ):
        op.drop_column("media_sources", column)
