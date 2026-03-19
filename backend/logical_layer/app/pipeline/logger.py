"""Fire-and-forget pipeline logger that writes to Org Layer logging endpoints."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from app.clients.organisational import OrganisationalClient
from app.utils import truncate_for_log, truncate_error

logger = logging.getLogger(__name__)


class StepContext:
    """Mutable context that a pipeline step populates during execution."""

    def __init__(self) -> None:
        self.output_summary: dict = {}
        self.metadata: dict = {}


class PipelineLogger:
    """Fire-and-forget logger that writes to Org Layer logging endpoints."""

    def __init__(
        self,
        org_client: OrganisationalClient,
        run_id: str,
        request_id: str,
    ):
        self.org = org_client
        self.run_id = run_id
        self.request_id = request_id
        self._step_order = 0
        self._audit_buffer: list[dict] = []
        self._steps_completed = 0
        self._steps_failed = 0

    async def start_run(self) -> None:
        """POST /api/logs/runs -- create the pipeline run record."""
        try:
            await self.org.create_run(
                run_id=self.run_id,
                request_id=self.request_id,
                started_at=_now_iso(),
            )
        except Exception as exc:
            logger.warning("Failed to start pipeline run: %s", exc)

    @asynccontextmanager
    async def step(
        self, step_name: str, input_summary: dict | None = None
    ) -> AsyncIterator[StepContext]:
        """Context manager that logs step start/end with timing."""
        self._step_order += 1
        order = self._step_order
        truncated_input = truncate_for_log(input_summary or {})

        entry_id = await self._create_entry(step_name, order, truncated_input)
        ctx = StepContext()
        start = time.monotonic()

        try:
            yield ctx
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._complete_entry(entry_id, duration_ms, ctx)
            self._steps_completed += 1
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            await self._fail_entry(entry_id, duration_ms, exc)
            self._steps_failed += 1
            raise

    def audit(
        self,
        category: str,
        level: str,
        step_name: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        """Buffer an audit log entry for batch flush."""
        self._audit_buffer.append(
            {
                "request_id": self.request_id,
                "run_id": self.run_id,
                "timestamp": _now_iso_ms(),
                "level": level,
                "category": category,
                "step_name": step_name,
                "message": message,
                "details": details or {},
                "source": "logical_layer",
            }
        )

    async def flush_audit(self) -> None:
        """POST /api/logs/audit/batch -- flush all buffered audit entries."""
        if not self._audit_buffer:
            return
        entries = self._audit_buffer.copy()
        self._audit_buffer.clear()
        try:
            await self.org.batch_audit_logs(entries)
        except Exception as exc:
            logger.warning("Failed to flush %d audit entries: %s", len(entries), exc)

    async def finalize_run(self, status: str, error_message: str | None = None) -> None:
        """PATCH /api/logs/runs/{run_id} -- mark run as completed/failed."""
        payload: dict[str, Any] = {
            "status": status,
            "completed_at": _now_iso(),
            "steps_completed": self._steps_completed,
            "steps_failed": self._steps_failed,
        }
        if error_message:
            payload["error_message"] = truncate_error(error_message)
        try:
            await self.org.update_run(self.run_id, **payload)
        except Exception as exc:
            logger.warning("Failed to finalize pipeline run: %s", exc)

    @property
    def collected_audit_entries(self) -> list[dict]:
        """Read-only access to the internal audit buffer for audit trail assembly."""
        return list(self._audit_buffer)

    # ── Internal helpers ──────────────────────────────────────

    async def _create_entry(
        self, step_name: str, step_order: int, input_summary: dict
    ) -> int | None:
        """Create a log entry and return its ID."""
        try:
            result = await self.org.create_entry(
                run_id=self.run_id,
                step_name=step_name,
                step_order=step_order,
                started_at=_now_iso(),
                input_summary=input_summary,
            )
            return result.get("id") if result else None
        except Exception as exc:
            logger.warning("Failed to create log entry for %s: %s", step_name, exc)
            return None

    async def _complete_entry(
        self, entry_id: int | None, duration_ms: int, ctx: StepContext
    ) -> None:
        """Mark a log entry as completed."""
        if entry_id is None:
            return
        try:
            await self.org.update_entry(
                entry_id,
                status="completed",
                completed_at=_now_iso(),
                duration_ms=duration_ms,
                output_summary=truncate_for_log(ctx.output_summary),
                metadata_=truncate_for_log(ctx.metadata),
            )
        except Exception as exc:
            logger.warning("Failed to complete log entry %s: %s", entry_id, exc)

    async def _fail_entry(
        self, entry_id: int | None, duration_ms: int, error: Exception
    ) -> None:
        """Mark a log entry as failed."""
        if entry_id is None:
            return
        try:
            await self.org.update_entry(
                entry_id,
                status="failed",
                completed_at=_now_iso(),
                duration_ms=duration_ms,
                error_message=truncate_error(str(error)),
            )
        except Exception as exc:
            logger.warning("Failed to mark log entry %s as failed: %s", entry_id, exc)


def _now_iso() -> str:
    """Current UTC time in ISO format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _now_iso_ms() -> str:
    """Current UTC time in ISO format with milliseconds."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3]
