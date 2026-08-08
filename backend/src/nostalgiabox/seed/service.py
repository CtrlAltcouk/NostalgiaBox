"""Transactional seed operation assembled from approved domain and repositories."""

from sqlalchemy import Engine, inspect, select
from sqlalchemy.orm import Session

from nostalgiabox.domain.models import Channel, ChannelId, MediaItem, MediaItemId
from nostalgiabox.domain.timeline import ChannelTimeline, build_sequential_timeline
from nostalgiabox.persistence.codecs import microseconds_to_timedelta
from nostalgiabox.persistence.errors import SeedConflictError, SeedSchemaMissingError
from nostalgiabox.persistence.media import StoredMediaItem
from nostalgiabox.persistence.models import ChannelRecord
from nostalgiabox.persistence.repositories import (
    ChannelRepository,
    MediaRepository,
    TimelineRepository,
)
from nostalgiabox.seed.manifest import SeedManifest

_REQUIRED_TABLES = frozenset({"media_items", "channels", "timeline_entries"})


def ensure_seed_schema(engine: Engine) -> None:
    """Fail clearly when migrations have not created the required schema."""
    missing_tables = _REQUIRED_TABLES.difference(inspect(engine).get_table_names())
    if missing_tables:
        missing = ", ".join(sorted(missing_tables))
        raise SeedSchemaMissingError(
            f"seed database schema is missing tables ({missing}); run 'alembic upgrade head' first"
        )


def seed_manifest(session: Session, manifest: SeedManifest) -> ChannelTimeline:
    """Upsert manifest state and replace only its channel timeline without committing."""
    channel = Channel(
        id=ChannelId(manifest.channel.id),
        number=manifest.channel.number,
        name=manifest.channel.name,
    )
    stored_media = tuple(
        StoredMediaItem(
            media_item=MediaItem(
                id=MediaItemId(item.id),
                title=item.title,
                duration=microseconds_to_timedelta(item.duration_us),
            ),
            path=item.path,
        )
        for item in manifest.media
    )
    timeline = build_sequential_timeline(
        channel,
        manifest.start_utc,
        tuple(item.media_item for item in stored_media),
    )

    number_owner = session.scalar(
        select(ChannelRecord).where(
            ChannelRecord.number == channel.number,
            ChannelRecord.id != channel.id.value,
        )
    )
    if number_owner is not None:
        raise SeedConflictError(
            f"channel number {channel.number} already belongs to channel {number_owner.id!r}"
        )

    media_repository = MediaRepository(session)
    channel_repository = ChannelRepository(session)
    timeline_repository = TimelineRepository(session)
    for item in stored_media:
        media_repository.store(item)
    channel_repository.store(channel)
    timeline_repository.replace(timeline)
    return timeline
