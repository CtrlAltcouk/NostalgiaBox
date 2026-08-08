"""Short-lived SQLAlchemy adapters for application runtime data ports."""

from sqlalchemy import Engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from nostalgiabox.application.runtime import (
    ChannelUnavailableError,
    MediaLocationUnavailableError,
)
from nostalgiabox.domain.models import Channel, ChannelId, MediaItemId
from nostalgiabox.domain.timeline import ChannelTimeline
from nostalgiabox.persistence.errors import RecordNotFoundError, RuntimeSchemaMissingError
from nostalgiabox.persistence.repositories import (
    ChannelRepository,
    MediaRepository,
    TimelineRepository,
)

_RUNTIME_TABLES = frozenset({"media_items", "channels", "timeline_entries"})


class SqlAlchemyRuntimeDataSource:
    """Implement runtime lookup ports with one closed session per operation."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def load(self, channel_id: ChannelId) -> ChannelTimeline:
        """Load a validated timeline without retaining its database session."""
        with self._session_factory() as session:
            try:
                return TimelineRepository(session).load(channel_id)
            except RecordNotFoundError as error:
                raise ChannelUnavailableError(str(error)) from error

    def get_path(self, media_item_id: MediaItemId) -> str:
        """Resolve one stored path without exposing StoredMediaItem to application code."""
        with self._session_factory() as session:
            stored_media = MediaRepository(session).get_by_id(media_item_id)
            if stored_media is None:
                raise MediaLocationUnavailableError(
                    f"media {media_item_id.value!r} has no persisted location"
                )
            return stored_media.path

    def get_by_number(self, channel_number: int) -> Channel:
        """Resolve the proof channel number or raise an application-level failure."""
        with self._session_factory() as session:
            channel = ChannelRepository(session).get_by_number(channel_number)
            if channel is None:
                raise ChannelUnavailableError(f"channel number {channel_number} was not found")
            return channel


def ensure_runtime_schema(engine: Engine) -> None:
    """Require the already-migrated Task 2.3 schema without creating or changing it."""
    missing = _RUNTIME_TABLES.difference(inspect(engine).get_table_names())
    if missing:
        names = ", ".join(sorted(missing))
        raise RuntimeSchemaMissingError(
            f"runtime database schema is missing tables ({names}); run 'alembic upgrade head' first"
        )
