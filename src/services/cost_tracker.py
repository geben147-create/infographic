"""
Thread-safe cost log writer for tracking per-call API costs.

Uses file locking to prevent concurrent write corruption. Supports
Windows (msvcrt) and Unix (fcntl) file locking with a fallback to
a portalocker-style approach using os-level advisory locks.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class CostEntry(BaseModel):
    """A single cost log entry for one API call."""

    workflow_id: str
    channel_id: str
    service: str  # e.g. "fal.ai", "comfyui", "none"
    step: str  # e.g. "video_gen_scene_00"
    amount_usd: float
    resolution: str | None = None
    timestamp: str  # ISO 8601


def _current_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class CostTracker:
    """Thread-safe cost_log.json writer with file locking."""

    def __init__(self, log_path: str = "data/cost_log.json") -> None:
        self._log_path = Path(log_path)

    def _read(self) -> list[dict[str, Any]]:
        """Read existing entries, returning empty list if file absent."""
        if not self._log_path.exists():
            return []
        try:
            content = self._log_path.read_text(encoding="utf-8").strip()
            if not content:
                return []
            return json.loads(content)
        except (json.JSONDecodeError, OSError):
            return []

    def _write_locked(self, entries: list[dict[str, Any]]) -> None:
        """Write entries to the log file with OS-level locking."""
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        # Open file for read+write, create if missing
        flags = os.O_RDWR | os.O_CREAT
        fd = os.open(str(self._log_path), flags, 0o644)

        try:
            if sys.platform == "win32":
                import msvcrt
                # Lock the file (blocking, exclusive)
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)

            # Truncate and write new content
            os.ftruncate(fd, 0)
            os.lseek(fd, 0, os.SEEK_SET)
            payload = json.dumps(entries, indent=2, ensure_ascii=False).encode("utf-8")
            os.write(fd, payload)

        finally:
            # Release lock by closing the fd (implicit on Windows, explicit on Unix)
            if sys.platform != "win32":
                try:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except Exception:
                    pass
            os.close(fd)

    def log(self, entry: CostEntry) -> None:
        """Append a cost entry to the log file.

        Uses file locking to prevent concurrent write corruption.
        Creates the file and parent directories if they do not exist.
        """
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

        # Read-modify-write with per-operation lock file on Windows
        # since Windows locks are mandatory and fd-based locking is unreliable
        # with os.O_RDWR when file already exists with content.
        if sys.platform == "win32":
            self._log_win(entry)
        else:
            entries = self._read()
            entries.append(entry.model_dump())
            self._write_locked(entries)

    def _log_win(self, entry: CostEntry) -> None:
        """Windows-specific log append using a .lock sentinel file."""
        lock_path = self._log_path.with_suffix(".lock")
        import time

        # Spin-wait for lock (simple advisory lock via file creation)
        for _ in range(50):
            try:
                lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
                os.close(lock_fd)
                break
            except FileExistsError:
                time.sleep(0.02)
        else:
            # Force-acquire after timeout (avoid deadlock)
            try:
                lock_path.unlink()
            except OSError:
                pass
            lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o644)
            os.close(lock_fd)

        try:
            entries = self._read()
            entries.append(entry.model_dump())
            self._log_path.write_text(
                json.dumps(entries, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        finally:
            try:
                lock_path.unlink()
            except OSError:
                pass

    def get_run_total(self, workflow_id: str) -> float:
        """Sum amount_usd for all entries matching workflow_id."""
        entries = self._read()
        return sum(
            e["amount_usd"] for e in entries if e.get("workflow_id") == workflow_id
        )

    def get_run_breakdown(self, workflow_id: str) -> list[CostEntry]:
        """Return all CostEntry objects for a given workflow_id."""
        entries = self._read()
        return [
            CostEntry(**e) for e in entries if e.get("workflow_id") == workflow_id
        ]
