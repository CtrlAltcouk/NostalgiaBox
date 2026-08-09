"""Structured stdout logging suitable for systemd and journald collection."""

import json
import logging
import logging.config
from datetime import UTC, datetime
from typing import Any

_STRUCTURED_FIELDS = (
    "action",
    "channel_id",
    "timeline_entry_id",
    "media_item_id",
    "now_utc",
    "entry_start_utc",
    "entry_end_utc",
    "target_live_offset",
    "target_live_offset_us",
    "logical_input_action",
    "input_profile",
    "input_outcome",
    "failure_category",
    "player_failure_type",
)


class JsonFormatter(logging.Formatter):
    """Serialize standard log records as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info is not None:
            payload["exception"] = self.formatException(record.exc_info)
        for field in _STRUCTURED_FIELDS:
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def configure_logging(level: str) -> None:
    """Configure process logging without creating application-owned log files."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {"json": {"()": JsonFormatter}},
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": "ext://sys.stdout",
                }
            },
            "root": {"handlers": ["console"], "level": level},
        }
    )
