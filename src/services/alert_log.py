"""
Structured alert logging to data/alerts.jsonl.

Append-only JSONL format. Each line is a JSON object:
{"ts": "2026-04-01T10:00:00Z", "level": "critical"|"warning", "message": "...", "details": "..."}
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone


_ALERT_LOG_PATH = pathlib.Path("data") / "alerts.jsonl"


def log_alert(level: str, message: str, details: str = "") -> None:
    """Append a structured alert entry to data/alerts.jsonl.

    Args:
        level: Alert severity — "critical" or "warning".
        message: Short description of the alert.
        details: Optional detailed context (stack trace, values, etc.).
    """
    _ALERT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "details": details,
    }
    with open(_ALERT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
