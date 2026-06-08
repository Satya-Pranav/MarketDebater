"""In-memory job manager for async debate runs.

Each `DebateJob` holds the event stream produced by `app.orchestrator.stream_debate`
so a separate HTTP request (the SSE endpoint) can fan those events back out to the
browser. The job also captures the assembled final result so the post-stream "rich
verdict" page can render without re-running the debate.

Constraints this assumes:
- Single gunicorn worker (multiple threads). Cross-process sharing isn't supported —
  if you bump workers > 1, jobs started on worker A won't be visible to worker B's
  SSE handler. The Procfile pins workers=1 for exactly this reason.
- Debates emit at most ~12 events (data, 3×rounds arguments, timings, verdict).
  Event list is bounded only by debate length, so we use a plain list (not deque).
"""
from __future__ import annotations

import threading
import time
import uuid
from typing import Any, Optional


class DebateJob:
    """A single in-flight or completed debate, identified by `id`."""

    def __init__(self, ticker: str, rounds: int) -> None:
        self.id: str = uuid.uuid4().hex
        self.ticker: str = ticker
        self.rounds: int = rounds
        self.created_at: float = time.time()
        self.events: list[dict[str, Any]] = []
        self.done: bool = False
        self.error: Optional[str] = None
        self.result: Optional[dict[str, Any]] = None
        # Whether this job's verdict was written to the leaderboard. Surfaced
        # to the rich-result template so the "Added to Daily Suggestions" pill
        # shows. Lives on the job (not inside result) so re-rendering the
        # result page doesn't drop the flag on the second visit.
        self.persisted: bool = False
        # One condition guards events + done so SSE consumers can block until
        # either a new event lands or the debate finishes.
        self._cv: threading.Condition = threading.Condition()

    def push(self, event: dict[str, Any]) -> None:
        with self._cv:
            self.events.append(event)
            self._cv.notify_all()

    def finish(
        self,
        result: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        with self._cv:
            self.done = True
            self.result = result
            self.error = error
            self._cv.notify_all()

    def wait_for_event(self, last_index: int, timeout: float = 10.0) -> int:
        """Block until events grow past `last_index` or the job finishes.

        Returns the current event count so the caller can slice events[last_index:].
        Also returns early on keepalive timeout so the SSE generator can flush a
        comment line and keep proxies from killing the idle connection.
        """
        with self._cv:
            deadline = time.time() + timeout
            while len(self.events) <= last_index and not self.done:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._cv.wait(timeout=remaining)
            return len(self.events)


_JOBS: dict[str, DebateJob] = {}
_JOBS_LOCK = threading.Lock()
# Drop jobs older than this so the in-memory dict doesn't grow without bound.
_MAX_JOB_AGE_SEC = 3600.0


def create_job(ticker: str, rounds: int) -> DebateJob:
    """Register a new job and return it."""
    _gc_old_jobs()
    job = DebateJob(ticker, rounds)
    with _JOBS_LOCK:
        _JOBS[job.id] = job
    return job


def get_job(job_id: str) -> Optional[DebateJob]:
    with _JOBS_LOCK:
        return _JOBS.get(job_id)


def _gc_old_jobs() -> None:
    """Opportunistic cleanup — called on each create_job."""
    now = time.time()
    with _JOBS_LOCK:
        stale = [jid for jid, j in _JOBS.items() if now - j.created_at > _MAX_JOB_AGE_SEC]
        for jid in stale:
            _JOBS.pop(jid, None)
