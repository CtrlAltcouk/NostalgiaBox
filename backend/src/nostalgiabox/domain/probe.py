"""Pure bounded technical-inspection values and conservative compatibility policy."""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum

_TEXT_LIMIT = 96
_FRAME_RATE_LIMIT = 1_000_000
_DIMENSION_LIMIT = 100_000
_DISPOSITION_LIMIT = 16


class ProbeDomainError(ValueError):
    """A probe payload cannot become a trusted domain fact."""


class ProbeFailureCode(StrEnum):
    EXECUTABLE_MISSING = "probe.executable_missing"
    VERSION_FAILED = "probe.version_failed"
    TIMEOUT = "probe.timeout"
    OUTPUT_TOO_LARGE = "probe.output_too_large"
    NONZERO_EXIT = "probe.nonzero_exit"
    MALFORMED_OUTPUT = "probe.malformed_output"
    CORRUPT_MEDIA = "probe.corrupt_media"
    INVALID_METADATA = "probe.invalid_metadata"
    EXECUTION_FAILED = "probe.execution_failed"


@dataclass(frozen=True, slots=True)
class ProbeFailure:
    """Sanitized failure evidence; raw subprocess output is never retained."""

    code: ProbeFailureCode
    message: str

    def __post_init__(self) -> None:
        if not self.message or len(self.message) > _TEXT_LIMIT:
            raise ProbeDomainError("probe failure message must be bounded and nonblank")


@dataclass(frozen=True, slots=True)
class StreamFact:
    """Bounded parsed fact for a supported ffprobe stream category."""

    codec_type: str
    codec_name: str | None = None
    language: str | None = None
    disposition: tuple[str, ...] = ()
    width: int | None = None
    height: int | None = None
    frame_rate_numerator: int | None = None
    frame_rate_denominator: int | None = None

    def __post_init__(self) -> None:
        if self.codec_type not in {"video", "audio", "subtitle"}:
            raise ProbeDomainError("unsupported stream type")
        if (self.width is None) != (self.height is None):
            raise ProbeDomainError("video dimensions must be paired")
        if self.width is not None and not 0 < self.width <= _DIMENSION_LIMIT:
            raise ProbeDomainError("width is outside accepted bounds")
        if self.height is not None and not 0 < self.height <= _DIMENSION_LIMIT:
            raise ProbeDomainError("height is outside accepted bounds")
        if (self.frame_rate_numerator is None) != (self.frame_rate_denominator is None):
            raise ProbeDomainError("frame rate must be paired")
        if self.codec_name is not None and (
            self.codec_name != normalized_text(self.codec_name)
            or len(self.codec_name) > _TEXT_LIMIT
        ):
            raise ProbeDomainError("codec name must be normalized and bounded")
        if self.language is not None and (
            self.language != normalized_text(self.language, limit=32) or len(self.language) > 32
        ):
            raise ProbeDomainError("language must be normalized and bounded")
        if (
            len(self.disposition) > _DISPOSITION_LIMIT
            or tuple(sorted(set(self.disposition))) != self.disposition
            or any(
                value != normalized_text(value, limit=32) or len(value) > 32
                for value in self.disposition
            )
        ):
            raise ProbeDomainError("disposition must be normalized, unique, and bounded")


@dataclass(frozen=True, slots=True)
class TechnicalMetadata:
    """Trusted facts for one exact discovery observation and capability policy."""

    duration_us: int
    containers: tuple[str, ...]
    streams: tuple[StreamFact, ...]
    observation_signature: str
    capability_version: str

    def __post_init__(self) -> None:
        if self.duration_us < 0:
            raise ProbeDomainError("duration must be non-negative microseconds")
        if not self.containers:
            raise ProbeDomainError("metadata requires at least one container")
        if not self.observation_signature.strip() or not self.capability_version.strip():
            raise ProbeDomainError("metadata requires nonblank versions")


def normalized_text(value: object, *, limit: int = _TEXT_LIMIT) -> str | None:
    """Return a bounded case-folded token; absent/unusable values become None."""
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).casefold()
    return normalized[:limit] if normalized else None


def decimal_duration_to_microseconds(value: str) -> int:
    """Convert decimal seconds to integer microseconds using ROUND_HALF_UP exactly."""
    try:
        seconds = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise ProbeDomainError("duration is not a decimal") from error
    if not seconds.is_finite() or seconds < 0:
        raise ProbeDomainError("duration must be finite and non-negative")
    return int((seconds * Decimal(1_000_000)).to_integral_value(rounding=ROUND_HALF_UP))


def parse_frame_rate(value: object) -> tuple[int, int] | None:
    """Parse a bounded positive rational; ``N/A`` and ``0/0`` mean unknown."""
    if value in (None, "", "0/0", "N/A"):
        return None
    if not isinstance(value, str) or value.count("/") != 1:
        raise ProbeDomainError("frame rate is not rational")
    numerator_text, denominator_text = value.split("/")
    if not numerator_text.isdecimal() or not denominator_text.isdecimal():
        raise ProbeDomainError("frame rate components must be unsigned integers")
    numerator, denominator = int(numerator_text), int(denominator_text)
    if not 0 < numerator <= _FRAME_RATE_LIMIT or not 0 < denominator <= _FRAME_RATE_LIMIT:
        raise ProbeDomainError("frame rate is outside accepted bounds")
    return numerator, denominator


def compatible(metadata: TechnicalMetadata) -> bool:
    """Conservative candidate policy; this never asserts verified player success."""
    return metadata.duration_us > 0 and any(
        stream.codec_type == "video"
        and stream.codec_name is not None
        and stream.width is not None
        and stream.height is not None
        for stream in metadata.streams
    )
