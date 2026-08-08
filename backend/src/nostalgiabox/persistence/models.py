"""SQLAlchemy 2 mappings for the approved Task 2.3 schema."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from nostalgiabox.persistence.base import Base

__all__ = ["Base", "ChannelRecord", "MediaItemRecord", "TimelineEntryRecord"]


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
