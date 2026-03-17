import json
import logging
import os
import queue
import threading
import urllib.error
import urllib.request
from typing import Optional

logger = logging.getLogger("llmobs")


class TraceCollector:
    """Background thread that drains a queue and POSTs traces to the collector API.

    Never raises — if the collector is unreachable the trace is silently dropped
    after logging a warning.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[dict] = queue.Queue(maxsize=1000)
        self._url: str = os.getenv("LLMOBS_COLLECTOR_URL", "http://localhost:8000")
        self._thread = threading.Thread(target=self._worker, name="llmobs-sender", daemon=True)
        self._thread.start()

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def enqueue(self, payload: dict) -> None:
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            logger.warning("llmobs: trace queue full, dropping trace")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _worker(self) -> None:
        while True:
            try:
                payload = self._queue.get(timeout=1)
                self._send(payload)
            except queue.Empty:
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning("llmobs: worker error: %s", exc)

    def _send(self, payload: dict) -> None:
        url = f"{self._url.rstrip('/')}/v1/traces/"
        data = json.dumps([payload]).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception as exc:  # noqa: BLE001
            logger.warning("llmobs: failed to send trace to %s: %s", url, exc)


# Module-level singleton
_collector: Optional[TraceCollector] = None
_lock = threading.Lock()


def get_collector() -> TraceCollector:
    global _collector
    if _collector is None:
        with _lock:
            if _collector is None:
                _collector = TraceCollector()
    return _collector
