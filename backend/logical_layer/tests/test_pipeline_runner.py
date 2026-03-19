"""Tests for the full pipeline runner."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.pipeline.runner import PipelineRunner


class TestPipelineRunner:
    @pytest.mark.asyncio
    async def test_full_pipeline_success(self, mock_org_client):
        runner = PipelineRunner(mock_org_client, None)
        result = await runner.process("REQ-000004")

        assert result.request_id == "REQ-000004"
        assert result.status in ("processed", "invalid")
        assert result.run_id != ""
        assert result.request_interpretation.category_l1 == "IT"
        assert result.request_interpretation.category_l2 == "Docking Stations"
        assert len(result.supplier_shortlist) > 0
        assert result.recommendation.status in ("proceed", "proceed_with_conditions", "cannot_proceed")

    @pytest.mark.asyncio
    async def test_pipeline_caches_result(self, mock_org_client):
        runner = PipelineRunner(mock_org_client, None)
        result = await runner.process("REQ-000004")
        cached = runner.get_cached_result("REQ-000004")
        assert cached is result

    @pytest.mark.asyncio
    async def test_pipeline_early_exit_missing_fields(self, mock_org_client_minimal):
        runner = PipelineRunner(mock_org_client_minimal, None)
        result = await runner.process("REQ-MINIMAL")

        assert result.status == "invalid"
        assert result.validation.completeness == "fail"
        assert len(result.escalations) > 0
        assert result.recommendation.status == "cannot_proceed"

    @pytest.mark.asyncio
    async def test_pipeline_updates_status(self, mock_org_client):
        runner = PipelineRunner(mock_org_client, None)
        await runner.process("REQ-000004")

        calls = mock_org_client.update_request_status.call_args_list
        assert len(calls) >= 2
        first_call_status = calls[0].args[1]
        assert first_call_status == "in_review"

    @pytest.mark.asyncio
    async def test_pipeline_creates_run(self, mock_org_client):
        runner = PipelineRunner(mock_org_client, None)
        await runner.process("REQ-000004")

        mock_org_client.create_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_persists_evaluation(self, mock_org_client):
        runner = PipelineRunner(mock_org_client, None)
        await runner.process("REQ-000004")

        mock_org_client.persist_evaluation_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_handles_org_error(self, mock_org_client):
        mock_org_client.get_request_overview = AsyncMock(
            side_effect=Exception("Org Layer down")
        )
        runner = PipelineRunner(mock_org_client, None)

        with pytest.raises(Exception, match="Org Layer down"):
            await runner.process("REQ-FAIL")

        mock_org_client.update_request_status.assert_any_call("REQ-FAIL", "error")

    @pytest.mark.asyncio
    async def test_get_cached_result_none(self, mock_org_client):
        runner = PipelineRunner(mock_org_client, None)
        assert runner.get_cached_result("REQ-NOTRUN") is None


class TestPipelineAuditTrail:
    @pytest.mark.asyncio
    async def test_audit_trail_populated(self, mock_org_client):
        runner = PipelineRunner(mock_org_client, None)
        result = await runner.process("REQ-000004")

        assert len(result.audit_trail.data_sources_used) > 0
        assert "requests.json" in result.audit_trail.data_sources_used
        assert len(result.audit_trail.supplier_ids_evaluated) > 0

    @pytest.mark.asyncio
    async def test_audit_trail_includes_policies(self, mock_org_client):
        runner = PipelineRunner(mock_org_client, None)
        result = await runner.process("REQ-000004")

        assert len(result.audit_trail.policies_checked) > 0

    @pytest.mark.asyncio
    async def test_audit_trail_historical_awards(self, mock_org_client):
        runner = PipelineRunner(mock_org_client, None)
        result = await runner.process("REQ-000004")

        assert result.audit_trail.historical_awards_consulted is True
        assert result.audit_trail.historical_award_note != ""
