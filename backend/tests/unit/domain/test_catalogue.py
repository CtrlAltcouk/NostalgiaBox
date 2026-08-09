"""Pure catalogue identity, locator and playable-range invariants."""

from datetime import timedelta

import pytest

from nostalgiabox.domain.catalogue import (
    CatalogueItemId,
    InvalidMediaFileError,
    InvalidPlayableRenditionError,
    MediaFile,
    MediaFileId,
    MediaSourceId,
    PlayableRendition,
    PlayableRenditionId,
    PreferredRenditionConflictError,
    RenditionOverlapError,
    validate_physical_duration,
    validate_rendition_set,
)
from nostalgiabox.domain.exceptions import InvalidIdentifierError


@pytest.mark.parametrize(
    "identifier_type",
    [CatalogueItemId, MediaSourceId, MediaFileId, PlayableRenditionId],
)
def test_catalogue_identifiers_reject_blank_values(identifier_type: type[object]) -> None:
    with pytest.raises(InvalidIdentifierError, match="must not be empty"):
        identifier_type("  ")  # type: ignore[call-arg]


def test_catalogue_identifiers_are_opaque_hashable_values() -> None:
    assert CatalogueItemId("same") == CatalogueItemId("same")
    assert CatalogueItemId("same") != object()
    assert {CatalogueItemId("same")} == {CatalogueItemId("same")}


@pytest.mark.parametrize(
    ("normalized", "original"),
    [
        ("", "show.mkv"),
        ("../show.mkv", "show.mkv"),
        ("series//show.mkv", "show.mkv"),
        ("/media/show.mkv", "show.mkv"),
        ("C:/media/show.mkv", "show.mkv"),
        ("series\\show.mkv", "show.mkv"),
        ("series/show.mkv", "..\\show.mkv"),
    ],
)
def test_media_file_rejects_non_relative_or_non_normalized_locators(
    normalized: str, original: str
) -> None:
    with pytest.raises(InvalidMediaFileError):
        _media_file(normalized, original)


def test_media_file_keeps_normalized_and_original_source_relative_locators() -> None:
    value = _media_file("Series One/Episode 01.mkv", "Series One\\Episode 01.mkv")

    assert value.normalized_relative_locator == "Series One/Episode 01.mkv"
    assert value.original_relative_locator == "Series One\\Episode 01.mkv"


def test_whole_file_rendition_has_exact_exclusive_bounds() -> None:
    rendition = _rendition("whole", start=0, duration=3_000_001, whole=True)

    assert rendition.segment_end == timedelta(microseconds=3_000_001)
    validate_physical_duration(rendition, rendition.segment_end)


@pytest.mark.parametrize(
    ("start", "duration", "logical", "whole"),
    [
        (-1, 10, 10, False),
        (0, 0, 10, False),
        (0, 10, 0, False),
        (0, 10, 11, False),
        (1, 10, 10, True),
        (0, 10, 9, True),
    ],
)
def test_rendition_rejects_invalid_exact_bounds(
    start: int, duration: int, logical: int, whole: bool
) -> None:
    with pytest.raises(InvalidPlayableRenditionError):
        _rendition("invalid", start=start, duration=duration, logical=logical, whole=whole)


def test_rendition_must_fit_measured_physical_duration() -> None:
    rendition = _rendition("bounded", start=5, duration=10, logical=8)

    with pytest.raises(InvalidPlayableRenditionError, match="exceeds"):
        validate_physical_duration(rendition, timedelta(microseconds=14))


def test_two_adjacent_episodes_can_share_one_media_file() -> None:
    episodes = (
        _rendition("episode-1", item="item-1", start=0, duration=100),
        _rendition("episode-2", item="item-2", start=100, duration=200),
    )

    validate_rendition_set(episodes)


def test_overlapping_episodes_on_one_file_are_rejected() -> None:
    episodes = (
        _rendition("episode-1", item="item-1", start=0, duration=101),
        _rendition("episode-2", item="item-2", start=100, duration=200),
    )

    with pytest.raises(RenditionOverlapError, match="overlap"):
        validate_rendition_set(episodes)


def test_catalogue_item_can_have_only_one_preferred_rendition() -> None:
    renditions = (
        _rendition("one", preferred=True),
        _rendition("two", file="file-2", preferred=True),
    )

    with pytest.raises(PreferredRenditionConflictError, match="preferred"):
        validate_rendition_set(renditions)


def _media_file(normalized: str, original: str) -> MediaFile:
    return MediaFile(
        id=MediaFileId("file-1"),
        source_id=MediaSourceId("source-1"),
        normalized_relative_locator=normalized,
        original_relative_locator=original,
    )


def _rendition(
    identifier: str,
    *,
    item: str = "item-1",
    file: str = "file-1",
    start: int = 0,
    duration: int = 10,
    logical: int | None = None,
    whole: bool = False,
    preferred: bool = False,
) -> PlayableRendition:
    return PlayableRendition(
        id=PlayableRenditionId(identifier),
        catalogue_item_id=CatalogueItemId(item),
        media_file_id=MediaFileId(file),
        segment_start=timedelta(microseconds=start),
        segment_duration=timedelta(microseconds=duration),
        logical_playable_duration=timedelta(microseconds=duration if logical is None else logical),
        is_whole_file=whole,
        preferred=preferred,
    )
