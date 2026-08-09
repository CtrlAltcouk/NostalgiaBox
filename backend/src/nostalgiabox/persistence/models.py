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
    """Minimum persisted source identity and technology kind."""

    __tablename__ = "media_sources"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_media_sources_id_nonblank"),
        CheckConstraint("kind IN ('local', 'smb')", name="ck_media_sources_kind"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, nullable=False)


class MediaFileRecord(Base):
    """A physical file with source-relative normalized and original locators."""

    __tablename__ = "media_files"
    __table_args__ = (
        UniqueConstraint(
            "source_id", "normalized_relative_locator", name="uq_media_files_source_locator"
        ),
        Index("ix_media_files_source", "source_id"),
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
