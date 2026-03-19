"""Async HTTP client for all Organisational Layer API calls."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 30.0
LOG_TIMEOUT = 10.0


class OrganisationalClient:
    """Wraps httpx.AsyncClient for typed access to every Org Layer endpoint."""

    def __init__(self, client: httpx.AsyncClient, base_url: str):
        self._client = client
        self._base = base_url.rstrip("/")

    # ── Data reads ────────────────────────────────────────────

    async def get_request_overview(self, request_id: str) -> dict:
        """GET /api/analytics/request-overview/{request_id}."""
        resp = await self._client.get(
            f"{self._base}/api/analytics/request-overview/{request_id}",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_escalations_by_request(self, request_id: str) -> list[dict]:
        """GET /api/escalations/by-request/{request_id}."""
        resp = await self._client.get(
            f"{self._base}/api/escalations/by-request/{request_id}",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_procurement_rules(
        self,
        rule_type: str | None = None,
        scope: str | None = None,
        enabled: bool = True,
        evaluation_mode: str | None = None,
    ) -> list[dict]:
        """GET /api/rules/definitions — fetches rule definitions with current version.

        Returns flat dicts compatible with the rule evaluator: each dict has
        rule_id, evaluation_mode, condition_expr, llm_prompt, trigger_template,
        action_target, is_blocking, severity, etc.
        """
        params = {}
        if rule_type:
            params["rule_type"] = rule_type
        if scope:
            params["scope"] = scope
        if enabled is not None:
            params["active"] = str(enabled).lower()
        if evaluation_mode:
            params["evaluation_mode"] = evaluation_mode
        resp = await self._client.get(
            f"{self._base}/api/rules/definitions",
            params=params or None,
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        raw = resp.json()
        return [self._flatten_rule(r) for r in raw]

    @staticmethod
    def _flatten_rule(r: dict) -> dict:
        """Merge rule_definition + current_version into flat evaluator dict."""
        config = {}
        cv = r.get("current_version")
        if cv and cv.get("rule_config"):
            config = cv["rule_config"]
        return {
            "rule_id": r.get("rule_id", ""),
            "evaluation_mode": r.get("evaluation_mode", "expression"),
            "condition_expr": config.get("condition_expr"),
            "llm_prompt": config.get("llm_prompt"),
            "trigger_template": r.get("trigger_template", ""),
            "action_target": r.get("action_target"),
            "is_blocking": r.get("is_blocking", True),
            "severity": r.get("severity", "high"),
            "enabled": r.get("active", True),
            "action_type": r.get("action_type", "escalate"),
            "field_ref": r.get("field_ref"),
            "action_required": r.get("action_required"),
            "breaks_completeness": r.get("breaks_completeness", False),
        }

    async def check_restricted(
        self,
        supplier_id: str,
        category_l1: str,
        category_l2: str,
        delivery_country: str,
    ) -> dict:
        """GET /api/analytics/check-restricted."""
        resp = await self._client.get(
            f"{self._base}/api/analytics/check-restricted",
            params={
                "supplier_id": supplier_id,
                "category_l1": category_l1,
                "category_l2": category_l2,
                "delivery_country": delivery_country,
            },
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    async def update_request_status(self, request_id: str, status: str) -> None:
        """PUT /api/requests/{request_id} with new status."""
        try:
            resp = await self._client.put(
                f"{self._base}/api/requests/{request_id}",
                json={"status": status},
                timeout=REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to update request status to %s: %s", status, exc)

    async def health_check(self) -> bool:
        """GET /health on the Org Layer."""
        try:
            resp = await self._client.get(f"{self._base}/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    # ── Pipeline run logging ──────────────────────────────────

    async def create_run(
        self, run_id: str, request_id: str, started_at: str
    ) -> dict | None:
        """POST /api/logs/runs."""
        try:
            resp = await self._client.post(
                f"{self._base}/api/logs/runs",
                json={
                    "run_id": run_id,
                    "request_id": request_id,
                    "started_at": started_at,
                },
                timeout=LOG_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Failed to create pipeline run: %s", exc)
            return None

    async def update_run(self, run_id: str, **kwargs: Any) -> None:
        """PATCH /api/logs/runs/{run_id}."""
        try:
            resp = await self._client.patch(
                f"{self._base}/api/logs/runs/{run_id}",
                json=kwargs,
                timeout=LOG_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to update pipeline run %s: %s", run_id, exc)

    async def create_entry(
        self,
        run_id: str,
        step_name: str,
        step_order: int,
        started_at: str,
        input_summary: dict | None = None,
    ) -> dict | None:
        """POST /api/logs/entries."""
        try:
            resp = await self._client.post(
                f"{self._base}/api/logs/entries",
                json={
                    "run_id": run_id,
                    "step_name": step_name,
                    "step_order": step_order,
                    "started_at": started_at,
                    "input_summary": input_summary or {},
                },
                timeout=LOG_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Failed to create log entry for %s: %s", step_name, exc)
            return None

    async def update_entry(self, entry_id: int, **kwargs: Any) -> None:
        """PATCH /api/logs/entries/{entry_id}. Uses metadata_ key for metadata."""
        try:
            resp = await self._client.patch(
                f"{self._base}/api/logs/entries/{entry_id}",
                json=kwargs,
                timeout=LOG_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to update log entry %s: %s", entry_id, exc)

    async def batch_audit_logs(self, entries: list[dict]) -> None:
        """POST /api/logs/audit/batch."""
        if not entries:
            return
        try:
            resp = await self._client.post(
                f"{self._base}/api/logs/audit/batch",
                json={"entries": entries},
                timeout=LOG_TIMEOUT,
            )
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Failed to batch audit logs (%d entries): %s", len(entries), exc)

    # ── Proxied reads (for status/audit routers) ─────────────

    async def get_runs(self, **filters: Any) -> dict:
        """GET /api/logs/runs with query filters."""
        resp = await self._client.get(
            f"{self._base}/api/logs/runs",
            params={k: v for k, v in filters.items() if v is not None},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_run(self, run_id: str) -> dict:
        """GET /api/logs/runs/{run_id}."""
        resp = await self._client.get(
            f"{self._base}/api/logs/runs/{run_id}",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_runs_by_request(self, request_id: str) -> list[dict]:
        """GET /api/logs/by-request/{request_id}."""
        resp = await self._client.get(
            f"{self._base}/api/logs/by-request/{request_id}",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_audit_by_request(self, request_id: str, **filters: Any) -> dict:
        """GET /api/logs/audit/by-request/{request_id}."""
        resp = await self._client.get(
            f"{self._base}/api/logs/audit/by-request/{request_id}",
            params={k: v for k, v in filters.items() if v is not None},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    async def get_audit_summary(self, request_id: str) -> dict:
        """GET /api/logs/audit/summary/{request_id}."""
        resp = await self._client.get(
            f"{self._base}/api/logs/audit/summary/{request_id}",
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
