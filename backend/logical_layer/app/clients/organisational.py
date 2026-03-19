"""HTTP client for the Organisational Layer API.

All data fetching from the database goes through this client — the logical
layer never connects to MySQL directly.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class OrganisationalClient:
    """Async wrapper around the Organisational Layer REST API."""

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = (base_url or settings.ORGANISATIONAL_LAYER_URL).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=30.0,
            )
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        r = await self.client.get("/health")
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Mega-endpoint (preferred entry point for the pipeline)
    # ------------------------------------------------------------------

    async def get_request_overview(self, request_id: str) -> dict[str, Any]:
        """Fetch the comprehensive pre-assembled evaluation package."""
        r = await self.client.get(f"/api/analytics/request-overview/{request_id}")
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Individual analytics endpoints (for targeted follow-up queries)
    # ------------------------------------------------------------------

    async def get_request(self, request_id: str) -> dict[str, Any]:
        r = await self.client.get(f"/api/requests/{request_id}")
        r.raise_for_status()
        return r.json()

    async def get_compliant_suppliers(
        self,
        category_l1: str,
        category_l2: str,
        delivery_country: str,
    ) -> list[dict[str, Any]]:
        r = await self.client.get(
            "/api/analytics/compliant-suppliers",
            params={
                "category_l1": category_l1,
                "category_l2": category_l2,
                "delivery_country": delivery_country,
            },
        )
        r.raise_for_status()
        return r.json()

    async def get_pricing_lookup(
        self,
        supplier_id: str,
        category_l1: str,
        category_l2: str,
        region: str,
        quantity: int,
    ) -> list[dict[str, Any]]:
        r = await self.client.get(
            "/api/analytics/pricing-lookup",
            params={
                "supplier_id": supplier_id,
                "category_l1": category_l1,
                "category_l2": category_l2,
                "region": region,
                "quantity": quantity,
            },
        )
        r.raise_for_status()
        return r.json()

    async def get_approval_tier(
        self, currency: str, amount: float
    ) -> dict[str, Any] | None:
        r = await self.client.get(
            "/api/analytics/approval-tier",
            params={"currency": currency, "amount": amount},
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()

    async def check_restricted(
        self,
        supplier_id: str,
        category_l1: str,
        category_l2: str,
        delivery_country: str,
    ) -> dict[str, Any]:
        r = await self.client.get(
            "/api/analytics/check-restricted",
            params={
                "supplier_id": supplier_id,
                "category_l1": category_l1,
                "category_l2": category_l2,
                "delivery_country": delivery_country,
            },
        )
        r.raise_for_status()
        return r.json()

    async def check_preferred(
        self,
        supplier_id: str,
        category_l1: str,
        category_l2: str,
        region: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {
            "supplier_id": supplier_id,
            "category_l1": category_l1,
            "category_l2": category_l2,
        }
        if region:
            params["region"] = region
        r = await self.client.get("/api/analytics/check-preferred", params=params)
        r.raise_for_status()
        return r.json()

    async def get_applicable_rules(
        self,
        category_l1: str,
        category_l2: str,
        delivery_country: str,
    ) -> dict[str, Any]:
        r = await self.client.get(
            "/api/analytics/applicable-rules",
            params={
                "category_l1": category_l1,
                "category_l2": category_l2,
                "delivery_country": delivery_country,
            },
        )
        r.raise_for_status()
        return r.json()

    async def get_awards_by_request(self, request_id: str) -> list[dict[str, Any]]:
        r = await self.client.get(f"/api/awards/by-request/{request_id}")
        r.raise_for_status()
        return r.json()

    async def get_escalation_rules(self) -> list[dict[str, Any]]:
        r = await self.client.get("/api/rules/escalation")
        r.raise_for_status()
        return r.json()

    async def get_escalations_by_request(self, request_id: str) -> list[dict[str, Any]]:
        r = await self.client.get(f"/api/escalations/by-request/{request_id}")
        if r.status_code == 404:
            return []
        r.raise_for_status()
        return r.json()

    async def get_supplier_win_rates(self) -> list[dict[str, Any]]:
        r = await self.client.get("/api/analytics/supplier-win-rates")
        r.raise_for_status()
        return r.json()

    # ------------------------------------------------------------------
    # Pipeline logging
    # ------------------------------------------------------------------

    async def create_pipeline_run(
        self, run_id: str, request_id: str, started_at: str
    ) -> dict[str, Any]:
        r = await self.client.post(
            "/api/logs/runs",
            json={"run_id": run_id, "request_id": request_id, "started_at": started_at},
        )
        r.raise_for_status()
        return r.json()

    async def update_pipeline_run(
        self, run_id: str, **fields: Any
    ) -> dict[str, Any]:
        r = await self.client.patch(f"/api/logs/runs/{run_id}", json=fields)
        r.raise_for_status()
        return r.json()

    async def create_log_entry(
        self, run_id: str, step_name: str, step_order: int,
        started_at: str, input_summary: Any | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "run_id": run_id,
            "step_name": step_name,
            "step_order": step_order,
            "started_at": started_at,
        }
        if input_summary is not None:
            payload["input_summary"] = input_summary
        r = await self.client.post("/api/logs/entries", json=payload)
        r.raise_for_status()
        return r.json()

    async def update_log_entry(
        self, entry_id: int, **fields: Any
    ) -> dict[str, Any]:
        r = await self.client.patch(f"/api/logs/entries/{entry_id}", json=fields)
        r.raise_for_status()
        return r.json()


org_client = OrganisationalClient()
