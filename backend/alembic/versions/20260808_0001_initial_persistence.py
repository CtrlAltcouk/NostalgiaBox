"""Create the initial NostalgiaBox persistence schema.

Revision ID: 20260808_0001
Revises:
Create Date: 2026-08-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260808_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the approved Task 2.3 tables, constraints and timeline index."""
    op.create_table(
        "media_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("duration_us", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(), nullable=False),
        sa.CheckConstraint("duration_us > 0", name="ck_media_items_duration_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "channels",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.CheckConstraint("number > 0", name="ck_channels_number_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("number", name="uq_channels_number"),
    )
    op.create_table(
        "timeline_entries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("channel_id", sa.String(), nullable=False),
        sa.Column("media_item_id", sa.String(), nullable=False),
        sa.Column("content_kind", sa.String(), nullable=False),
        sa.Column("start_utc_us", sa.Integer(), nullable=False),
        sa.Column("end_utc_us", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "end_utc_us > start_utc_us",
            name="ck_timeline_entries_valid_interval",
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["media_item_id"], ["media_items.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel_id",
            "start_utc_us",
            name="uq_timeline_entries_channel_start",
        ),
    )
    op.create_index(
        "ix_timeline_entries_channel_start",
        "timeline_entries",
        ["channel_id", "start_utc_us"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the initial persistence schema in dependency order."""
    op.drop_index("ix_timeline_entries_channel_start", table_name="timeline_entries")
    op.drop_table("timeline_entries")
    op.drop_table("channels")
    op.drop_table("media_items")
