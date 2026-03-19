"""Shared fixtures for logical layer tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from typing import Any

import pytest
import httpx
from fastapi.testclient import TestClient

from app.clients.organisational import OrganisationalClient
from app.clients.llm import LLMClient
from app.models.common import (
    ApprovalTierData,
    AwardData,
    EscalationData,
    PricingData,
    RequestData,
    RulesData,
    CategoryRule,
    GeographyRule,
    SupplierData,
)
from app.models.pipeline_io import (
    ComplianceResult,
    EnrichedSupplier,
    EscalationResult,
    Escalation,
    ExcludedSupplier,
    FetchResult,
    FilterResult,
    RankedSupplier,
    RankResult,
    RecommendationResult,
    ValidationIssue,
    ValidationResult,
    RequestInterpretation,
    PolicyResult,
    ApprovalThresholdEval,
    PreferredSupplierEval,
)
from app.pipeline.logger import PipelineLogger


# ── Sample data ───────────────────────────────────────────────────────


SAMPLE_REQUEST_OVERVIEW = {
    "request": {
        "request_id": "REQ-000004",
        "created_at": "2026-03-14T17:55:00",
        "request_channel": "teams",
        "request_language": "en",
        "business_unit": "Digital Workplace",
        "country": "DE",
        "site": "Berlin",
        "requester_id": "USR-3004",
        "requester_role": "Workplace Lead",
        "submitted_for_id": "USR-8004",
        "category_l1": "IT",
        "category_l2": "Docking Stations",
        "title": "Docking station purchase",
        "request_text": (
            "Need 240 docking stations matching existing laptop fleet. "
            "Must be delivered by 2026-03-20 with premium specification. "
            "Budget capped at 25 199.55 EUR. Please use Dell Enterprise Europe with no exception."
        ),
        "currency": "EUR",
        "budget_amount": "25199.55",
        "quantity": "240",
        "unit_of_measure": "device",
        "required_by_date": "2026-03-20",
        "preferred_supplier_mentioned": "Dell Enterprise Europe",
        "incumbent_supplier": "Bechtle Workplace Solutions",
        "contract_type_requested": "purchase",
        "delivery_countries": ["DE"],
        "data_residency_constraint": False,
        "esg_requirement": False,
        "status": "pending_review",
        "scenario_tags": ["contradictory"],
    },
    "compliant_suppliers": [
        {
            "supplier_id": "SUP-0001",
            "supplier_name": "Dell Enterprise Europe",
            "country_hq": "DE",
            "currency": "EUR",
            "quality_score": 85,
            "risk_score": 15,
            "esg_score": 73,
            "preferred_supplier": True,
            "data_residency_supported": True,
            "capacity_per_month": 18000,
        },
        {
            "supplier_id": "SUP-0007",
            "supplier_name": "Bechtle Workplace Solutions",
            "country_hq": "DE",
            "currency": "EUR",
            "quality_score": 82,
            "risk_score": 12,
            "esg_score": 78,
            "preferred_supplier": True,
            "data_residency_supported": True,
            "capacity_per_month": 8000,
        },
        {
            "supplier_id": "SUP-0002",
            "supplier_name": "HP Enterprise Devices",
            "country_hq": "NL",
            "currency": "EUR",
            "quality_score": 80,
            "risk_score": 19,
            "esg_score": 68,
            "preferred_supplier": False,
            "data_residency_supported": False,
            "capacity_per_month": 16000,
        },
    ],
    "pricing": [
        {
            "pricing_id": "PR-00019",
            "supplier_id": "SUP-0001",
            "supplier_name": "Dell Enterprise Europe",
            "region": "EU",
            "currency": "EUR",
            "min_quantity": 100,
            "max_quantity": 499,
            "unit_price": "142.50",
            "expedited_unit_price": "156.75",
            "total_price": "34200.00",
            "expedited_total_price": "37620.00",
            "standard_lead_time_days": 14,
            "expedited_lead_time_days": 7,
            "moq": 100,
        },
        {
            "pricing_id": "PR-00069",
            "supplier_id": "SUP-0007",
            "supplier_name": "Bechtle Workplace Solutions",
            "region": "EU",
            "currency": "EUR",
            "min_quantity": 100,
            "max_quantity": 499,
            "unit_price": "148.80",
            "expedited_unit_price": "163.68",
            "total_price": "35712.00",
            "expedited_total_price": "39283.20",
            "standard_lead_time_days": 16,
            "expedited_lead_time_days": 9,
            "moq": 100,
        },
        {
            "pricing_id": "PR-00029",
            "supplier_id": "SUP-0002",
            "supplier_name": "HP Enterprise Devices",
            "region": "EU",
            "currency": "EUR",
            "min_quantity": 100,
            "max_quantity": 499,
            "unit_price": "155.00",
            "expedited_unit_price": "170.50",
            "total_price": "37200.00",
            "expedited_total_price": "40920.00",
            "standard_lead_time_days": 18,
            "expedited_lead_time_days": 10,
            "moq": 100,
        },
    ],
    "applicable_rules": {
        "category_rules": [
            {
                "rule_id": "CR-001",
                "category_id": 5,
                "rule_type": "mandatory_comparison",
                "rule_text": "IT hardware purchases must include at least 2 comparable quotes.",
            }
        ],
        "geography_rules": [],
    },
    "approval_tier": {
        "threshold_id": "AT-002",
        "currency": "EUR",
        "min_amount": "25000.00",
        "max_amount": "99999.99",
        "min_supplier_quotes": 2,
        "policy_note": None,
        "managers": ["business", "procurement"],
        "deviation_approvers": ["Procurement Manager"],
    },
    "historical_awards": [
        {
            "award_id": "AWD-000010",
            "supplier_id": "SUP-0007",
            "supplier_name": "Bechtle Workplace Solutions",
            "total_value": "35000.00",
            "currency": "EUR",
            "awarded": True,
            "award_rank": 1,
            "decision_rationale": "Best overall value",
            "savings_pct": "3.50",
            "lead_time_days": 14,
        }
    ],
}

SAMPLE_ESCALATIONS_BY_REQUEST: list[dict] = []


SAMPLE_REQUEST_OVERVIEW_MINIMAL = {
    "request": {
        "request_id": "REQ-MINIMAL",
        "category_l1": None,
        "category_l2": None,
        "currency": None,
        "budget_amount": None,
        "quantity": None,
        "country": "DE",
        "delivery_countries": [],
        "data_residency_constraint": False,
        "esg_requirement": False,
        "status": "pending_review",
    },
    "compliant_suppliers": [],
    "pricing": [],
    "applicable_rules": {"category_rules": [], "geography_rules": []},
    "approval_tier": None,
    "historical_awards": [],
}

SAMPLE_RESTRICTION_CHECK = {"supplier_id": "SUP-0002", "is_restricted": False}


# ── Fixtures ───────────────────────────────────────────────────────


@pytest.fixture
def mock_org_client() -> OrganisationalClient:
    """Create an OrganisationalClient with all methods mocked."""
    client = MagicMock(spec=OrganisationalClient)

    client.get_request_overview = AsyncMock(return_value=SAMPLE_REQUEST_OVERVIEW)
    client.get_escalations_by_request = AsyncMock(return_value=SAMPLE_ESCALATIONS_BY_REQUEST)
    client.check_restricted = AsyncMock(return_value=SAMPLE_RESTRICTION_CHECK)
    client.update_request_status = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    client.create_run = AsyncMock(return_value={"id": 1, "run_id": "test-run"})
    client.update_run = AsyncMock()
    client.create_entry = AsyncMock(return_value={"id": 1})
    client.update_entry = AsyncMock()
    client.batch_audit_logs = AsyncMock()
    client.get_runs_by_request = AsyncMock(return_value=[{"run_id": "test-run", "status": "completed"}])
    client.get_runs = AsyncMock(return_value={"items": [], "total": 0})
    client.get_run = AsyncMock(return_value={"run_id": "test-run"})
    client.get_audit_by_request = AsyncMock(return_value={"items": [], "total": 0})
    client.get_audit_summary = AsyncMock(return_value={"request_id": "REQ-000004", "total_entries": 0})
    client.persist_evaluation_run = AsyncMock(return_value={"evaluation_run_id": 1})

    return client


@pytest.fixture
def mock_org_client_minimal() -> OrganisationalClient:
    """Org client that returns a minimal (incomplete) request."""
    client = MagicMock(spec=OrganisationalClient)

    client.get_request_overview = AsyncMock(return_value=SAMPLE_REQUEST_OVERVIEW_MINIMAL)
    client.get_escalations_by_request = AsyncMock(return_value=[])
    client.check_restricted = AsyncMock(return_value={"is_restricted": False})
    client.update_request_status = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    client.create_run = AsyncMock(return_value={"id": 1, "run_id": "test-run"})
    client.update_run = AsyncMock()
    client.create_entry = AsyncMock(return_value={"id": 1})
    client.update_entry = AsyncMock()
    client.batch_audit_logs = AsyncMock()
    client.persist_evaluation_run = AsyncMock(return_value={"evaluation_run_id": 1})

    return client


@pytest.fixture
def pipeline_logger(mock_org_client) -> PipelineLogger:
    return PipelineLogger(mock_org_client, "test-run-id", "REQ-000004")


@pytest.fixture
def sample_request() -> RequestData:
    return RequestData.model_validate(SAMPLE_REQUEST_OVERVIEW["request"])


@pytest.fixture
def sample_fetch_result() -> FetchResult:
    raw = SAMPLE_REQUEST_OVERVIEW
    return FetchResult(
        request=RequestData.model_validate(raw["request"]),
        compliant_suppliers=[SupplierData.model_validate(s) for s in raw["compliant_suppliers"]],
        pricing=[PricingData.model_validate(p) for p in raw["pricing"]],
        applicable_rules=RulesData.model_validate(raw["applicable_rules"]),
        approval_tier=ApprovalTierData.model_validate(raw["approval_tier"]),
        historical_awards=[AwardData.model_validate(a) for a in raw["historical_awards"]],
        org_escalations=[],
    )


@pytest.fixture
def sample_enriched_suppliers() -> list[EnrichedSupplier]:
    return [
        EnrichedSupplier(
            supplier_id="SUP-0001",
            supplier_name="Dell Enterprise Europe",
            country_hq="DE",
            currency="EUR",
            quality_score=85,
            risk_score=15,
            esg_score=73,
            preferred_supplier=True,
            data_residency_supported=True,
            capacity_per_month=18000,
            pricing_id="PR-00019",
            unit_price=142.50,
            total_price=34200.00,
            expedited_unit_price=156.75,
            expedited_total_price=37620.00,
            standard_lead_time_days=14,
            expedited_lead_time_days=7,
            pricing_tier_applied="100-499 units",
            has_pricing=True,
        ),
        EnrichedSupplier(
            supplier_id="SUP-0007",
            supplier_name="Bechtle Workplace Solutions",
            country_hq="DE",
            currency="EUR",
            quality_score=82,
            risk_score=12,
            esg_score=78,
            preferred_supplier=True,
            data_residency_supported=True,
            capacity_per_month=8000,
            pricing_id="PR-00069",
            unit_price=148.80,
            total_price=35712.00,
            expedited_unit_price=163.68,
            expedited_total_price=39283.20,
            standard_lead_time_days=16,
            expedited_lead_time_days=9,
            pricing_tier_applied="100-499 units",
            has_pricing=True,
        ),
        EnrichedSupplier(
            supplier_id="SUP-0002",
            supplier_name="HP Enterprise Devices",
            country_hq="NL",
            currency="EUR",
            quality_score=80,
            risk_score=19,
            esg_score=68,
            preferred_supplier=False,
            data_residency_supported=False,
            capacity_per_month=16000,
            pricing_id="PR-00029",
            unit_price=155.00,
            total_price=37200.00,
            expedited_unit_price=170.50,
            expedited_total_price=40920.00,
            standard_lead_time_days=18,
            expedited_lead_time_days=10,
            pricing_tier_applied="100-499 units",
            has_pricing=True,
        ),
    ]


@pytest.fixture
def sample_filter_result(sample_enriched_suppliers) -> FilterResult:
    return FilterResult(
        enriched_suppliers=sample_enriched_suppliers,
        suppliers_without_pricing=[],
    )


@pytest.fixture
def sample_compliance_result(sample_enriched_suppliers) -> ComplianceResult:
    return ComplianceResult(
        compliant=sample_enriched_suppliers,
        excluded=[],
    )


@pytest.fixture
def sample_rank_result() -> RankResult:
    return RankResult(
        ranked_suppliers=[
            RankedSupplier(
                rank=1,
                supplier_id="SUP-0001",
                supplier_name="Dell Enterprise Europe",
                preferred=True,
                incumbent=False,
                pricing_tier_applied="100-499 units",
                unit_price=142.50,
                total_price=34200.00,
                expedited_unit_price=156.75,
                expedited_total_price=37620.00,
                standard_lead_time_days=14,
                expedited_lead_time_days=7,
                quality_score=85,
                risk_score=15,
                esg_score=73,
                true_cost=47294.12,
                overpayment=13094.12,
                currency="EUR",
            ),
            RankedSupplier(
                rank=2,
                supplier_id="SUP-0007",
                supplier_name="Bechtle Workplace Solutions",
                preferred=True,
                incumbent=True,
                pricing_tier_applied="100-499 units",
                unit_price=148.80,
                total_price=35712.00,
                expedited_unit_price=163.68,
                expedited_total_price=39283.20,
                standard_lead_time_days=16,
                expedited_lead_time_days=9,
                quality_score=82,
                risk_score=12,
                esg_score=78,
                true_cost=52000.00,
                overpayment=16288.00,
                currency="EUR",
            ),
        ],
        ranking_method="true_cost",
    )


@pytest.fixture
def sample_validation_result(sample_request) -> ValidationResult:
    return ValidationResult(
        completeness=True,
        issues=[
            ValidationIssue(
                issue_id="V-001",
                severity="critical",
                type="budget_insufficient",
                description="Budget of EUR 25,199.55 cannot cover 240 units.",
                action_required="Increase budget.",
            ),
        ],
        request_interpretation=RequestInterpretation(
            category_l1="IT",
            category_l2="Docking Stations",
            quantity=240,
            unit_of_measure="device",
            budget_amount=25199.55,
            currency="EUR",
            delivery_country="DE",
            required_by_date="2026-03-20",
            days_until_required=6,
            preferred_supplier_stated="Dell Enterprise Europe",
            incumbent_supplier="Bechtle Workplace Solutions",
        ),
    )


@pytest.fixture
def sample_escalation_result() -> EscalationResult:
    return EscalationResult(
        escalations=[
            Escalation(
                escalation_id="ESC-001",
                rule="ER-001",
                trigger="Budget insufficient",
                escalate_to="Requester Clarification",
                blocking=True,
                source="pipeline",
            ),
        ],
        has_blocking=True,
        blocking_count=1,
        non_blocking_count=0,
    )


@pytest.fixture
def app_with_mocks(mock_org_client):
    """Create a FastAPI TestClient with mocked dependencies."""
    from app.main import app
    from app.pipeline.runner import PipelineRunner

    app.state.org_client = mock_org_client
    app.state.llm_client = None
    app.state.pipeline_runner = PipelineRunner(mock_org_client, None)
    return TestClient(app)
