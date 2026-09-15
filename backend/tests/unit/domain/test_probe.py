"""Pure bounded probe facts and policy tests."""

import pytest

from nostalgiabox.domain.probe import (
    ProbeDomainError,
    StreamFact,
    TechnicalMetadata,
    compatible,
    decimal_duration_to_microseconds,
    parse_frame_rate,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1.0000005", 1_000_001), ("0.0000004", 0), ("2", 2_000_000)],
)
def test_duration_is_exact_decimal_half_up(value: str, expected: int) -> None:
    assert decimal_duration_to_microseconds(value) == expected


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "not-a-number"])
def test_duration_rejects_nonfinite_or_invalid(value: str) -> None:
    with pytest.raises(ProbeDomainError):
        decimal_duration_to_microseconds(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("30000/1001", (30000, 1001)), ("0/0", None), ("N/A", None)],
)
def test_frame_rate_rules(value: str, expected: tuple[int, int] | None) -> None:
    assert parse_frame_rate(value) == expected


@pytest.mark.parametrize("value", ["1/0", "-1/2", "1.5/2", "1000001/1", "1/2/3"])
def test_frame_rate_rejects_invalid(value: str) -> None:
    with pytest.raises(ProbeDomainError):
        parse_frame_rate(value)


def test_stream_facts_require_paired_dimensions_and_rates() -> None:
    with pytest.raises(ProbeDomainError, match="dimensions"):
        StreamFact("video", width=1)
    with pytest.raises(ProbeDomainError, match="frame rate"):
        StreamFact("video", frame_rate_numerator=1)


def test_compatibility_is_conservative_policy_not_playability() -> None:
    candidate = TechnicalMetadata(
        1,
        ("matroska",),
        (StreamFact("video", "h264", width=10, height=10),),
        "sig",
        "v1",
    )
    audio_only = TechnicalMetadata(
        1,
        ("mp3",),
        (StreamFact("audio", "mp3"),),
        "sig",
        "v1",
    )

    assert compatible(candidate)
    assert not compatible(audio_only)


def test_stream_fact_rejects_non_normalized_or_unbounded_text_facts() -> None:
    with pytest.raises(ProbeDomainError, match="codec"):
        StreamFact("video", " H264 ")
    with pytest.raises(ProbeDomainError, match="language"):
        StreamFact("audio", language="EN")
    with pytest.raises(ProbeDomainError, match="disposition"):
        StreamFact("subtitle", disposition=("Forced",))
