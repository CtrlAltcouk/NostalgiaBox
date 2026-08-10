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
    "ScanIssueRecord",
    "ScanRunRecord",
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
        CheckConstraint(
            "presence IN ('unclassified', 'present', 'missing')",
            name="ck_media_files_presence",
        ),
        CheckConstraint(
            "size_bytes IS NULL OR size_bytes >= 0",
            name="ck_media_files_size_nonnegative",
        ),
        CheckConstraint(
            "last_seen_generation IS NULL OR last_seen_generation >= 1",
            name="ck_media_files_seen_generation_positive",
        ),
        CheckConstraint(
            "(presence = 'unclassified' AND size_bytes IS NULL AND modified_time_ns IS NULL "
            "AND device_id IS NULL AND inode_id IS NULL AND last_seen_generation IS NULL "
            "AND first_observed_utc_us IS NULL AND last_observed_utc_us IS NULL "
            "AND missing_since_utc_us IS NULL) OR "
            "(presence IN ('present', 'missing') AND size_bytes IS NOT NULL "
            "AND modified_time_ns IS NOT NULL AND last_seen_generation IS NOT NULL "
            "AND first_observed_utc_us IS NOT NULL AND last_observed_utc_us IS NOT NULL)",
            name="ck_media_files_observation_state",
        ),
        CheckConstraint(
            "(presence = 'missing') = (missing_since_utc_us IS NOT NULL)",
            name="ck_media_files_missing_timestamp",
        ),
        Index(
            "ix_media_files_source_locator",
            "source_id",
            "normalized_relative_locator",
        ),
        Index("ix_media_files_source_presence", "source_id", "presence"),
        Index("ix_media_files_source_generation", "source_id", "last_seen_generation"),
        Index(
            "uq_media_files_present_source_locator",
            "source_id",
            "normalized_relative_locator",
            unique=True,
            sqlite_where=text("presence = 'present'"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("media_sources.id", ondelete="RESTRICT"), nullable=False
    )
    normalized_relative_locator: Mapped[str] = mapped_column(String, nullable=False)
    original_relative_locator: Mapped[str] = mapped_column(String, nullable=False)
    presence: Mapped[str] = mapped_column(String, nullable=False, default="unclassified")
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modified_time_ns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    device_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inode_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_generation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_observed_utc_us: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_observed_utc_us: Mapped[int | None] = mapped_column(Integer, nullable=True)
    missing_since_utc_us: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ScanRunRecord(Base):
    """Durable per-source scan execution and bounded progress state."""

    __tablename__ = "scan_runs"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_scan_runs_id_nonblank"),
        CheckConstraint("kind IN ('full', 'incremental')", name="ck_scan_runs_kind"),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'cancelled', 'interrupted', 'failed')",
            name="ck_scan_runs_status",
        ),
        CheckConstraint("generation >= 1", name="ck_scan_runs_generation_positive"),
        CheckConstraint(
            "cancellation_requested IN (0, 1)", name="ck_scan_runs_cancellation_boolean"
        ),
        CheckConstraint(
            "discovered_count >= 0 AND added_count >= 0 AND unchanged_count >= 0 "
            "AND changed_count >= 0 AND missing_count >= 0 AND ignored_count >= 0 "
            "AND issue_count >= 0",
            name="ck_scan_runs_counts_nonnegative",
        ),
        CheckConstraint(
            "added_count + unchanged_count + changed_count <= discovered_count",
            name="ck_scan_runs_outcomes_within_discovered",
        ),
        CheckConstraint(
            "(source_revision IS NULL) = (source_root IS NULL)",
            name="ck_scan_runs_source_snapshot_pair",
        ),
        CheckConstraint(
            "source_revision IS NULL OR source_revision >= 1",
            name="ck_scan_runs_source_revision_positive",
        ),
        CheckConstraint(
            "source_root IS NULL OR length(trim(source_root)) > 0",
            name="ck_scan_runs_source_root_nonblank",
        ),
        CheckConstraint(
            "(terminal_error_code IS NULL) = (terminal_error_message IS NULL)",
            name="ck_scan_runs_error_pair",
        ),
        CheckConstraint(
            "terminal_error_code IS NULL OR length(trim(terminal_error_code)) > 0",
            name="ck_scan_runs_error_code_nonblank",
        ),
        CheckConstraint(
            "terminal_error_message IS NULL OR length(trim(terminal_error_message)) > 0",
            name="ck_scan_runs_error_message_nonblank",
        ),
        CheckConstraint(
            "(status = 'queued' AND started_utc_us IS NULL AND finished_utc_us IS NULL) OR "
            "(status = 'running' AND started_utc_us IS NOT NULL AND finished_utc_us IS NULL) OR "
            "(status = 'completed' AND started_utc_us IS NOT NULL "
            "AND finished_utc_us IS NOT NULL) OR "
            "(status IN ('cancelled', 'interrupted', 'failed') "
            "AND finished_utc_us IS NOT NULL)",
            name="ck_scan_runs_status_timestamps",
        ),
        UniqueConstraint("source_id", "generation", name="uq_scan_runs_source_generation"),
        Index("ix_scan_runs_source_queued", "source_id", "queued_utc_us"),
        Index("ix_scan_runs_status", "status"),
        Index(
            "uq_scan_runs_active_source",
            "source_id",
            unique=True,
            sqlite_where=text("status IN ('queued', 'running')"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("media_sources.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[str] = mapped_column(String, nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    queued_utc_us: Mapped[int] = mapped_column(Integer, nullable=False)
    started_utc_us: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finished_utc_us: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_root: Mapped[str | None] = mapped_column(String, nullable=True)
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    changed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    missing_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ignored_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    issue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    terminal_error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    terminal_error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class ScanIssueRecord(Base):
    """Sanitized idempotent issue attached to one durable scan run."""

    __tablename__ = "scan_issues"
    __table_args__ = (
        CheckConstraint("length(trim(id)) > 0", name="ck_scan_issues_id_nonblank"),
        CheckConstraint("length(trim(deduplication_key)) > 0", name="ck_scan_issues_key_nonblank"),
        CheckConstraint("length(trim(code)) > 0", name="ck_scan_issues_code_nonblank"),
        CheckConstraint("length(trim(message)) > 0", name="ck_scan_issues_message_nonblank"),
        CheckConstraint("severity IN ('info', 'warning', 'error')", name="ck_scan_issues_severity"),
        UniqueConstraint("run_id", "deduplication_key", name="uq_scan_issues_run_key"),
        Index("ix_scan_issues_run_occurred", "run_id", "occurred_utc_us"),
        Index("ix_scan_issues_code", "code"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("scan_runs.id", ondelete="CASCADE"), nullable=False
    )
    media_file_id: Mapped[str | None] = mapped_column(
        ForeignKey("media_files.id", ondelete="RESTRICT"), nullable=True
    )
    relative_locator: Mapped[str | None] = mapped_column(String, nullable=True)
    deduplication_key: Mapped[str] = mapped_column(String, nullable=False)
    code: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    occurred_utc_us: Mapped[int] = mapped_column(Integer, nullable=False)


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
