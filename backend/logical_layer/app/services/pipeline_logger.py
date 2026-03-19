"""Structured pipeline logger that persists step-level telemetry to the
Organisational Layer's logging API.

Usage inside the processing pipeline::

    logger = await PipelineLogger.start(request_id)
    async with logger.step("fetch_request", input_summary={"request_id": rid}):
        data = await org_client.get_request(rid)
    ...
    await logger.finish()

All logging calls are *fire-and-forget safe*: if the Org Layer is unreachable
the pipeline continues without interruption.
"""

from __future__ import annotations

import contextlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from app.clients.organisational import org_client

_log = logging.getLogger(__name__)

MAX_SUMMARY_KEYS = 30
MAX_SUMMARY_STR_LEN = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _truncate_value(v: Any, depth: int = 0) -> Any:
    """Recursively truncate a value for safe JSON storage."""
    if depth > 3:
        return "..."
    if isinstance(v, str):
        return v[:MAX_SUMMARY_STR_LEN] + ("..." if len(v) > MAX_SUMMARY_STR_LEN else "")
    if isinstance(v, dict):
        items = list(v.items())[:MAX_SUMMARY_KEYS]
        return {k: _truncate_value(val, depth + 1) for k, val in items}
    if isinstance(v, (list, tuple)):
        if len(v) <= 5:
            return [_truncate_value(i, depth + 1) for i in v]
        return {
            "_type": "list",
            "_length": len(v),
            "_sample": [_truncate_value(i, depth + 1) for i in v[:3]],
        }
    return v


def truncate_summary(data: Any) -> Any:
    """Produce a JSON-safe truncated summary of arbitrary pipeline data."""
    if data is None:
        return None
    try:
        return _truncate_value(data)
    except Exception:
        return {"_error": "could not serialize summary"}


class PipelineLogger:
    """Async context-manager based logger that records each pipeline step."""

    def __init__(self, run_id: str, request_id: str) -> None:
        self.run_id = run_id
        self.request_id = request_id
        self._step_order = 0
        self._steps_completed = 0
        self._steps_failed = 0
        self._t0 = time.monotonic()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @classmethod
    async def start(cls, request_id: str) -> PipelineLogger:
        """Create a new pipeline run in the DB and return a logger."""
        run_id = str(uuid.uuid4())
        try:
            await org_client.create_pipeline_run(run_id, request_id, _now_iso())
        except Exception:
            _log.warning("Failed to create pipeline run for %s — logging disabled", request_id)
        return cls(run_id=run_id, request_id=request_id)

    async def finish(self, status: str = "completed", error_message: str | None = None) -> None:
        """Mark the pipeline run as finished."""
        duration_ms = int((time.monotonic() - self._t0) * 1000)
        try:
            fields: dict[str, Any] = {
                "status": status,
                "completed_at": _now_iso(),
                "total_duration_ms": duration_ms,
                "steps_completed": self._steps_completed,
                "steps_failed": self._steps_failed,
            }
            if error_message:
                fields["error_message"] = error_message[:2000]
            await org_client.update_pipeline_run(self.run_id, **fields)
        except Exception:
            _log.warning("Failed to finalize pipeline run %s", self.run_id)

    # ------------------------------------------------------------------
    # Step context manager
    # ------------------------------------------------------------------

    @contextlib.asynccontextmanager
    async def step(self, step_name: str, input_summary: Any = None):
        """Wrap a pipeline step with automatic timing and logging.

        Yields control to the caller; on success records the step as
        ``completed``, on exception records it as ``failed`` then re-raises.
        """
        self._step_order += 1
        order = self._step_order
        entry_id: int | None = None

        try:
            resp = await org_client.create_log_entry(
                run_id=self.run_id,
                step_name=step_name,
                step_order=order,
                started_at=_now_iso(),
                input_summary=truncate_summary(input_summary),
            )
            entry_id = resp.get("id")
        except Exception:
            _log.warning("Failed to create log entry for step %s", step_name)

        t0 = time.monotonic()
        try:
            yield
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._steps_failed += 1
            if entry_id is not None:
                try:
                    await org_client.update_log_entry(
                        entry_id,
                        status="failed",
                        completed_at=_now_iso(),
                        duration_ms=duration_ms,
                        error_message=str(exc)[:2000],
                    )
                except Exception:
                    _log.warning("Failed to update log entry %s", entry_id)
            raise
        else:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._steps_completed += 1
            if entry_id is not None:
                try:
                    await org_client.update_log_entry(
                        entry_id,
                        status="completed",
                        completed_at=_now_iso(),
                        duration_ms=duration_ms,
                    )
                except Exception:
                    _log.warning("Failed to update log entry %s", entry_id)

    async def log_step_output(self, entry_id: int | None, output_summary: Any = None, metadata: Any = None) -> None:
        """Attach output_summary / metadata to an already-completed entry."""
        if entry_id is None:
            return
        try:
            fields: dict[str, Any] = {}
            if output_summary is not None:
                fields["output_summary"] = truncate_summary(output_summary)
            if metadata is not None:
                fields["metadata_"] = metadata
            if fields:
                await org_client.update_log_entry(entry_id, **fields)
        except Exception:
            _log.warning("Failed to attach output to log entry %s", entry_id)

    @contextlib.asynccontextmanager
    async def step_with_output(self, step_name: str, input_summary: Any = None):
        """Like ``step`` but yields a dict that the caller can populate with
        ``output_summary`` and ``metadata`` keys.  They are flushed after the
        step completes successfully.
        """
        self._step_order += 1
        order = self._step_order
        entry_id: int | None = None
        result_bag: dict[str, Any] = {}

        try:
            resp = await org_client.create_log_entry(
                run_id=self.run_id,
                step_name=step_name,
                step_order=order,
                started_at=_now_iso(),
                input_summary=truncate_summary(input_summary),
            )
            entry_id = resp.get("id")
        except Exception:
            _log.warning("Failed to create log entry for step %s", step_name)

        t0 = time.monotonic()
        try:
            yield result_bag
        except Exception as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._steps_failed += 1
            if entry_id is not None:
                try:
                    await org_client.update_log_entry(
                        entry_id,
                        status="failed",
                        completed_at=_now_iso(),
                        duration_ms=duration_ms,
                        error_message=str(exc)[:2000],
                    )
                except Exception:
                    _log.warning("Failed to update log entry %s", entry_id)
            raise
        else:
            duration_ms = int((time.monotonic() - t0) * 1000)
            self._steps_completed += 1
            if entry_id is not None:
                try:
                    update_fields: dict[str, Any] = {
                        "status": "completed",
                        "completed_at": _now_iso(),
                        "duration_ms": duration_ms,
                    }
                    if "output_summary" in result_bag:
                        update_fields["output_summary"] = truncate_summary(result_bag["output_summary"])
                    if "metadata" in result_bag:
                        update_fields["metadata_"] = result_bag["metadata"]
                    await org_client.update_log_entry(entry_id, **update_fields)
                except Exception:
                    _log.warning("Failed to update log entry %s", entry_id)
