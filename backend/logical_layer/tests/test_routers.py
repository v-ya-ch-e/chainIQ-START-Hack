"""Tests for API router endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_check(self, app_with_mocks):
        response = app_with_mocks.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["org_layer"] == "reachable"
        assert data["llm"] == "not_configured"

    def test_health_check_org_unreachable(self, app_with_mocks, mock_org_client):
        mock_org_client.health_check = AsyncMock(return_value=False)
        response = app_with_mocks.get("/health")
        data = response.json()
        assert data["org_layer"] == "unreachable"


class TestPipelineProcessEndpoint:
    def test_process_success(self, app_with_mocks):
        response = app_with_mocks.post(
            "/api/pipeline/process",
            json={"request_id": "REQ-000004"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "REQ-000004"
        assert "request_interpretation" in data
        assert "validation" in data
        assert "recommendation" in data

    def test_process_not_found(self, app_with_mocks, mock_org_client):
        mock_org_client.get_request_overview = AsyncMock(
            side_effect=Exception("404 Not Found")
        )
        response = app_with_mocks.post(
            "/api/pipeline/process",
            json={"request_id": "REQ-NOTFOUND"},
        )
        assert response.status_code == 404

    def test_process_internal_error(self, app_with_mocks, mock_org_client):
        mock_org_client.get_request_overview = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        response = app_with_mocks.post(
            "/api/pipeline/process",
            json={"request_id": "REQ-ERROR"},
        )
        assert response.status_code == 500


class TestBatchProcessEndpoint:
    def test_batch_accepted(self, app_with_mocks):
        response = app_with_mocks.post(
            "/api/pipeline/process-batch",
            json={"request_ids": ["REQ-000001", "REQ-000002"], "concurrency": 2},
        )
        assert response.status_code == 202
        data = response.json()
        assert data["queued"] == 2
        assert data["concurrency"] == 2
        assert "batch_id" in data


class TestStatusEndpoint:
    def test_status_found(self, app_with_mocks):
        response = app_with_mocks.post(
            "/api/pipeline/process",
            json={"request_id": "REQ-000004"},
        )
        assert response.status_code == 200

        response = app_with_mocks.get("/api/pipeline/status/REQ-000004")
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "REQ-000004"

    def test_status_not_found(self, app_with_mocks, mock_org_client):
        mock_org_client.get_runs_by_request = AsyncMock(return_value=[])
        response = app_with_mocks.get("/api/pipeline/status/REQ-NOTFOUND")
        assert response.status_code == 404


class TestResultEndpoint:
    def test_result_found_after_process(self, app_with_mocks):
        app_with_mocks.post(
            "/api/pipeline/process",
            json={"request_id": "REQ-000004"},
        )
        response = app_with_mocks.get("/api/pipeline/result/REQ-000004")
        assert response.status_code == 200
        data = response.json()
        assert data["request_id"] == "REQ-000004"

    def test_result_not_found(self, app_with_mocks):
        response = app_with_mocks.get("/api/pipeline/result/REQ-NEVER")
        assert response.status_code == 404


class TestRunsEndpoint:
    def test_list_runs(self, app_with_mocks):
        response = app_with_mocks.get("/api/pipeline/runs")
        assert response.status_code == 200


class TestAuditEndpoint:
    def test_audit_trail(self, app_with_mocks):
        response = app_with_mocks.get("/api/pipeline/audit/REQ-000004")
        assert response.status_code == 200

    def test_audit_summary(self, app_with_mocks):
        response = app_with_mocks.get("/api/pipeline/audit/REQ-000004/summary")
        assert response.status_code == 200


class TestStepEndpoints:
    def test_fetch_step(self, app_with_mocks):
        response = app_with_mocks.post(
            "/api/pipeline/steps/fetch",
            json={"request_id": "REQ-000004"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "request" in data
        assert "compliant_suppliers" in data

    def test_validate_step(self, app_with_mocks):
        response = app_with_mocks.post(
            "/api/pipeline/steps/validate",
            json={"request_id": "REQ-000004"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "completeness" in data
        assert "issues" in data

    def test_filter_step(self, app_with_mocks):
        response = app_with_mocks.post(
            "/api/pipeline/steps/filter",
            json={"request_id": "REQ-000004"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "enriched_suppliers" in data

    def test_comply_step(self, app_with_mocks):
        response = app_with_mocks.post(
            "/api/pipeline/steps/comply",
            json={"request_id": "REQ-000004"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "compliant" in data
        assert "excluded" in data

    def test_rank_step(self, app_with_mocks):
        response = app_with_mocks.post(
            "/api/pipeline/steps/rank",
            json={"request_id": "REQ-000004"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "ranked_suppliers" in data
        assert "ranking_method" in data

    def test_escalate_step(self, app_with_mocks):
        response = app_with_mocks.post(
            "/api/pipeline/steps/escalate",
            json={"request_id": "REQ-000004"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "escalations" in data
        assert "has_blocking" in data
