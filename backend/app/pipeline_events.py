"""
Central event bus for the pipeline.
Holds per-user cancel flags and log queues — imported by both nodes.py and main.py
without creating circular imports.
"""
from __future__ import annotations

import queue
import threading
from datetime import datetime, timezone

# ── Per-user state ─────────────────────────────────────────────────────────────

_cancel_flags: dict[str, threading.Event] = {}
_log_queues: dict[str, queue.Queue] = {}


def _cancel_flag(user_id: str) -> threading.Event:
    if user_id not in _cancel_flags:
        _cancel_flags[user_id] = threading.Event()
    return _cancel_flags[user_id]


def _log_queue(user_id: str) -> queue.Queue:
    if user_id not in _log_queues:
        _log_queues[user_id] = queue.Queue(maxsize=500)
    return _log_queues[user_id]


# ── Public API ─────────────────────────────────────────────────────────────────

def emit(user_id: str, message: str, level: str = "info") -> None:
    """Push a log entry onto the user's queue (non-blocking, drops on full)."""
    q = _log_queue(user_id)
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
    }
    try:
        q.put_nowait(entry)
    except queue.Full:
        # Drop oldest, make room
        try:
            q.get_nowait()
            q.put_nowait(entry)
        except Exception:
            pass


def emit_done(user_id: str) -> None:
    """Push sentinel None to signal the SSE stream that the pipeline finished."""
    q = _log_queue(user_id)
    try:
        q.put_nowait(None)
    except queue.Full:
        pass


def drain_logs(user_id: str) -> queue.Queue:
    """Return the raw queue so the SSE endpoint can poll it."""
    return _log_queue(user_id)


def is_cancelled(user_id: str) -> bool:
    return _cancel_flag(user_id).is_set()


def cancel_pipeline(user_id: str) -> None:
    _cancel_flag(user_id).set()
    emit(user_id, "Stop requested — cancelling after current step…", level="warn")


def reset_pipeline(user_id: str) -> None:
    """Clear cancel flag and flush stale log entries before a new run."""
    _cancel_flag(user_id).clear()
    q = _log_queue(user_id)
    while not q.empty():
        try:
            q.get_nowait()
        except Exception:
            break


def cancel_all() -> None:
    """Called on server shutdown to stop all in-flight pipelines."""
    for flag in _cancel_flags.values():
        flag.set()
