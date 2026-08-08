"""Persistence-side association between domain media and a source path."""

from dataclasses import dataclass

from nostalgiabox.domain.models import MediaItem
from nostalgiabox.persistence.errors import InvalidStoredMediaError


@dataclass(frozen=True, slots=True)
class StoredMediaItem:
    """Approved domain media metadata paired with an infrastructure path."""

    media_item: MediaItem
    path: str

    def __post_init__(self) -> None:
        if not self.path.strip():
            raise InvalidStoredMediaError("stored media path must not be empty")
