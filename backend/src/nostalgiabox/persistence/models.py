"""SQLAlchemy 2 mappings for the approved Task 2.3 schema."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from nostalgiabox.persistence.base import Base

__all__ = [
    "Base",
    "CatalogueItemRecord",
    "ChannelRecord",
    "MediaFileRecord",
    "MediaItemRecord",
    "MediaSourceRecord",
    "PlayableRenditionRecord",
    "TimelineEntryRecord",
]


class CatalogueItemRecord(Base):
    """Stable logical catalogue identity, including temporarily unplayable items."""

    __tablename__ = "catalogue_items"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_catalogue_items_id_nonblank"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)


class MediaSourceRecord(Base):
    """Persisted source configuration, lifecycle and sanitized availability."""

    __tablename__ = "media_sources"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_media_sources_id_nonblank"),
        CheckConstraint("kind IN ('local', 'smb')", name="ck_media_sources_kind"),
        CheckConstraint(
            "display_name IS NULL OR length(trim(display_name)) > 0",
            name="ck_media_sources_display_name_nonblank",
        ),
        CheckConstraint(
            "configured_root IS NULL OR length(trim(configured_root)) > 0",
            name="ck_media_sources_configured_root_nonblank",
        ),
        CheckConstraint("enabled IN (0, 1)", name="ck_media_sources_enabled_boolean"),
        CheckConstraint(
            "availability IN ('unknown', 'available', 'unavailable', "
            "'authentication_failed', 'permission_denied', 'invalid_root', 'error')",
            name="ck_media_sources_availability",
        ),
        CheckConstraint(
            "current_error_code IS NULL OR length(trim(current_error_code)) > 0",
            name="ck_media_sources_error_code_nonblank",
        ),
        CheckConstraint(
            "current_error_message IS NULL OR length(trim(current_error_message)) > 0",
            name="ck_media_sources_error_message_nonblank",
        ),
        CheckConstraint(
            "(current_error_code IS NULL) = (current_error_message IS NULL)",
            name="ck_media_sources_error_pair",
        ),
        CheckConstraint(
            "retired_utc_us IS NULL OR enabled = 0",
            name="ck_media_sources_retired_disabled",
        ),
        CheckConstraint("revision >= 1", name="ck_media_sources_revision_positive"),
        Index("ix_media_sources_enabled_availability", "enabled", "availability"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    configured_root: Mapped[str | None] = mapped_column(String, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    availability: Mapped[str] = mapped_column(String, nullable=False, default="unknown")
    last_checked_utc_us: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_successful_scan_utc_us: Mapped[int | None] = mapped_column(Integer, nullable=True)
    current_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    current_error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    retired_utc_us: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class MediaFileRecord(Base):
    """A physical file with source-relative normalized and original locators."""

    __tablename__ = "media_files"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_media_files_id_nonblank"),
        CheckConstraint(
            "length(trim(normalized_relative_locator)) > 0",
            name="ck_media_files_normalized_locator_nonblank",
        ),
        CheckConstraint(
            "length(trim(original_relative_locator)) > 0",
            name="ck_media_files_original_locator_nonblank",
        ),
        Index(
            "ix_media_files_source_locator",
            "source_id",
            "normalized_relative_locator",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("media_sources.id", ondelete="RESTRICT"), nullable=False
    )
    normalized_relative_locator: Mapped[str] = mapped_column(String, nullable=False)
    original_relative_locator: Mapped[str] = mapped_column(String, nullable=False)


class PlayableRenditionRecord(Base):
    """A persisted whole-file or bounded playable range."""

    __tablename__ = "playable_renditions"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_renditions_id_nonblank"),
        CheckConstraint("segment_start_us >= 0", name="ck_renditions_start_nonnegative"),
        CheckConstraint("segment_duration_us > 0", name="ck_renditions_duration_positive"),
        CheckConstraint("logical_playable_duration_us > 0", name="ck_renditions_logical_positive"),
        CheckConstraint(
            "logical_playable_duration_us <= segment_duration_us",
            name="ck_renditions_logical_within_segment",
        ),
        CheckConstraint(
            "is_whole_file = 0 OR (segment_start_us = 0 AND "
            "logical_playable_duration_us = segment_duration_us)",
            name="ck_renditions_whole_file",
        ),
        Index("ix_renditions_catalogue_item", "catalogue_item_id"),
        Index("ix_renditions_media_file", "media_file_id"),
        Index(
            "uq_renditions_preferred_catalogue_item",
            "catalogue_item_id",
            unique=True,
            sqlite_where=text("preferred = 1"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    catalogue_item_id: Mapped[str] = mapped_column(
        ForeignKey("catalogue_items.id", ondelete="RESTRICT"), nullable=False
    )
    media_file_id: Mapped[str] = mapped_column(
        ForeignKey("media_files.id", ondelete="RESTRICT"), nullable=False
    )
    segment_start_us: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_duration_us: Mapped[int] = mapped_column(Integer, nullable=False)
    logical_playable_duration_us: Mapped[int] = mapped_column(Integer, nullable=False)
    is_whole_file: Mapped[bool] = mapped_column(Boolean, nullable=False)
    preferred: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MediaItemRecord(Base):
    """Persistent media metadata plus its infrastructure-owned path."""

    __tablename__ = "media_items"
    __table_args__ = (CheckConstraint("duration_us > 0", name="ck_media_items_duration_positive"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    duration_us: Mapped[int] = mapped_column(Integer, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)


class ChannelRecord(Base):
    """Persistent channel identity and display fields."""

    __tablename__ = "channels"
    __table_args__ = (
        CheckConstraint("number > 0", name="ck_channels_number_positive"),
        UniqueConstraint("number", name="uq_channels_number"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)


class TimelineEntryRecord(Base):
    """Persistent absolute UTC interval and domain references."""

    __tablename__ = "timeline_entries"
    __table_args__ = (
        CheckConstraint("end_utc_us > start_utc_us", name="ck_timeline_entries_valid_interval"),
        UniqueConstraint(
            "channel_id",
            "start_utc_us",
            name="uq_timeline_entries_channel_start",
        ),
        Index("ix_timeline_entries_channel_start", "channel_id", "start_utc_us"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    channel_id: Mapped[str] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    media_item_id: Mapped[str] = mapped_column(
        ForeignKey("media_items.id"),
        nullable=False,
    )
    content_kind: Mapped[str] = mapped_column(String, nullable=False)
    start_utc_us: Mapped[int] = mapped_column(Integer, nullable=False)
    end_utc_us: Mapped[int] = mapped_column(Integer, nullable=False)
