"""Validated external manifest models for the Channel 001 proof seed."""

import json
from datetime import datetime
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nostalgiabox.domain.time import normalize_utc


class ChannelManifest(BaseModel):
    """Manifest representation of the proof channel."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    number: int = Field(gt=0)
    name: str = Field(min_length=1)


class MediaManifest(BaseModel):
    """Manifest representation of supplied media metadata and location."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    duration_us: int = Field(gt=0)
    path: str = Field(min_length=1)


class SeedManifest(BaseModel):
    """Complete input needed to construct one deterministic proof timeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    channel: ChannelManifest
    start_utc: datetime
    media: tuple[MediaManifest, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_domain_boundaries(self) -> Self:
        """Normalize the start and reject duplicate stable media identities."""
        normalized_start = normalize_utc(self.start_utc, field_name="seed start_utc")
        object.__setattr__(self, "start_utc", normalized_start)
        media_ids = [item.id for item in self.media]
        if len(media_ids) != len(set(media_ids)):
            raise ValueError("seed manifest media IDs must be unique")
        return self


def load_manifest(path: Path) -> SeedManifest:
    """Read and validate a user-supplied JSON manifest."""
    raw_manifest = json.loads(path.read_text(encoding="utf-8"))
    return SeedManifest.model_validate(raw_manifest)
