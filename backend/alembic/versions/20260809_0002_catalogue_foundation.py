"""Add the Phase 3 catalogue foundation without altering Phase 2 rows.

Revision ID: 20260809_0002
Revises: 20260808_0001
Create Date: 2026-08-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260809_0002"
down_revision: str | Sequence[str] | None = "20260808_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create catalogue tables and backfill same-ID logical items."""
    connection = op.get_bind()
    invalid_id = connection.execute(
        sa.text("SELECT id FROM media_items WHERE length(trim(id)) = 0 LIMIT 1")
    ).scalar_one_or_none()
    if invalid_id is not None:
        raise RuntimeError("catalogue migration rejected a blank legacy media_items.id")

    op.create_table(
        "catalogue_items",
        sa.Column("id", sa.String(), nullable=False),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_catalogue_items_id_nonblank"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "media_sources",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_media_sources_id_nonblank"),
        sa.CheckConstraint("kind IN ('local', 'smb')", name="ck_media_sources_kind"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "media_files",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("source_id", sa.String(), nullable=False),
        sa.Column("normalized_relative_locator", sa.String(), nullable=False),
        sa.Column("original_relative_locator", sa.String(), nullable=False),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_media_files_id_nonblank"),
        sa.CheckConstraint(
            "length(trim(normalized_relative_locator)) > 0",
            name="ck_media_files_normalized_locator_nonblank",
        ),
        sa.CheckConstraint(
            "length(trim(original_relative_locator)) > 0",
            name="ck_media_files_original_locator_nonblank",
        ),
        sa.ForeignKeyConstraint(["source_id"], ["media_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_media_files_source_locator",
        "media_files",
        ["source_id", "normalized_relative_locator"],
    )
    op.create_table(
        "playable_renditions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("catalogue_item_id", sa.String(), nullable=False),
        sa.Column("media_file_id", sa.String(), nullable=False),
        sa.Column("segment_start_us", sa.Integer(), nullable=False),
        sa.Column("segment_duration_us", sa.Integer(), nullable=False),
        sa.Column("logical_playable_duration_us", sa.Integer(), nullable=False),
        sa.Column("is_whole_file", sa.Boolean(), nullable=False),
        sa.Column("preferred", sa.Boolean(), nullable=False),
        sa.CheckConstraint("length(trim(id)) > 0", name="ck_renditions_id_nonblank"),
        sa.CheckConstraint("segment_start_us >= 0", name="ck_renditions_start_nonnegative"),
        sa.CheckConstraint("segment_duration_us > 0", name="ck_renditions_duration_positive"),
        sa.CheckConstraint(
            "logical_playable_duration_us > 0", name="ck_renditions_logical_positive"
        ),
        sa.CheckConstraint(
            "logical_playable_duration_us <= segment_duration_us",
            name="ck_renditions_logical_within_segment",
        ),
        sa.CheckConstraint(
            "is_whole_file = 0 OR (segment_start_us = 0 AND "
            "logical_playable_duration_us = segment_duration_us)",
            name="ck_renditions_whole_file",
        ),
        sa.ForeignKeyConstraint(["catalogue_item_id"], ["catalogue_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["media_file_id"], ["media_files.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_renditions_catalogue_item", "playable_renditions", ["catalogue_item_id"])
    op.create_index("ix_renditions_media_file", "playable_renditions", ["media_file_id"])
    op.create_index(
        "uq_renditions_preferred_catalogue_item",
        "playable_renditions",
        ["catalogue_item_id"],
        unique=True,
        sqlite_where=sa.text("preferred = 1"),
    )
    connection.execute(sa.text("INSERT INTO catalogue_items (id) SELECT id FROM media_items"))


def downgrade() -> None:
    """Remove only the additive Phase 3 foundation."""
    op.drop_index("uq_renditions_preferred_catalogue_item", table_name="playable_renditions")
    op.drop_index("ix_renditions_media_file", table_name="playable_renditions")
    op.drop_index("ix_renditions_catalogue_item", table_name="playable_renditions")
    op.drop_table("playable_renditions")
    op.drop_index("ix_media_files_source_locator", table_name="media_files")
    op.drop_table("media_files")
    op.drop_table("media_sources")
    op.drop_table("catalogue_items")
