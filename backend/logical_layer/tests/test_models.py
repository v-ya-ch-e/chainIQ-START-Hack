"""Tests for Pydantic model validation and edge cases."""

from __future__ import annotations

import pytest

from app.models.common import (
    ApprovalTierData,
    EscalationData,
    PricingData,
    RequestData,
    SupplierData,
)
from app.models.output import PipelineOutput, RecommendationOutput
from app.models.pipeline_io import (
    EnrichedSupplier,
    RankedSupplier,
    ValidationIssue,
)


class TestRequestData:
    def test_minimal(self):
        r = RequestData(request_id="REQ-001")
        assert r.request_id == "REQ-001"
        assert r.category_l1 is None
        assert r.delivery_countries == []
        assert r.data_residency_constraint is False

    def test_full_from_dict(self):
        r = RequestData.model_validate({
            "request_id": "REQ-004",
            "category_l1": "IT",
            "category_l2": "Docking Stations",
            "currency": "EUR",
            "budget_amount": "25199.55",
            "quantity": "240",
            "delivery_countries": ["DE"],
            "data_residency_constraint": False,
            "esg_requirement": False,
        })
        assert r.budget_amount == "25199.55"
        assert r.quantity == "240"

    def test_extra_fields_allowed(self):
        r = RequestData.model_validate({
            "request_id": "REQ-X",
            "extra_field": "hello",
        })
        assert r.request_id == "REQ-X"


class TestSupplierData:
    def test_defaults(self):
        s = SupplierData(supplier_id="SUP-001")
        assert s.quality_score == 0
        assert s.preferred_supplier is False
        assert s.capacity_per_month is None

    def test_from_dict(self):
        s = SupplierData.model_validate({
            "supplier_id": "SUP-001",
            "supplier_name": "Dell",
            "quality_score": 85,
            "risk_score": 15,
            "capacity_per_month": 18000,
        })
        assert s.capacity_per_month == 18000


class TestApprovalTierData:
    def test_eur_schema(self):
        t = ApprovalTierData.model_validate({
            "threshold_id": "AT-002",
            "currency": "EUR",
            "min_amount": "25000.00",
            "max_amount": "99999.99",
            "min_supplier_quotes": 2,
            "managers": ["business", "procurement"],
            "deviation_approvers": ["Procurement Manager"],
        })
        assert t.get_quotes_required() == 2
        assert t.get_approvers() == ["business", "procurement"]
        assert t.get_min_amount() == 25000.0
        assert t.get_max_amount() == 99999.99

    def test_usd_schema(self):
        t = ApprovalTierData.model_validate({
            "threshold_id": "AT-006",
            "currency": "USD",
            "min_value": "0",
            "max_value": "24999.99",
            "quotes_required": 1,
            "approvers": ["business"],
        })
        assert t.get_quotes_required() == 1
        assert t.get_approvers() == ["business"]
        assert t.get_min_amount() == 0.0

    def test_missing_amounts(self):
        t = ApprovalTierData(threshold_id="AT-X")
        assert t.get_min_amount() == 0.0
        assert t.get_max_amount() == 999_999_999.0
        assert t.get_quotes_required() == 1


class TestPricingData:
    def test_from_dict(self):
        p = PricingData.model_validate({
            "pricing_id": "PR-001",
            "supplier_id": "SUP-001",
            "unit_price": "142.50",
            "min_quantity": 100,
            "max_quantity": 499,
            "total_price": "34200.00",
        })
        assert p.unit_price == "142.50"

    def test_defaults(self):
        p = PricingData(supplier_id="SUP-001")
        assert p.min_quantity == 0
        assert p.max_quantity == 999999


class TestEnrichedSupplier:
    def test_with_pricing(self):
        es = EnrichedSupplier(
            supplier_id="SUP-001",
            unit_price=100.0,
            total_price=24000.0,
            has_pricing=True,
        )
        assert es.has_pricing is True

    def test_without_pricing(self):
        es = EnrichedSupplier(
            supplier_id="SUP-001",
            has_pricing=False,
        )
        assert es.unit_price is None
        assert es.total_price is None


class TestRankedSupplier:
    def test_defaults(self):
        rs = RankedSupplier(supplier_id="SUP-001")
        assert rs.rank == 0
        assert rs.true_cost is None
        assert rs.policy_compliant is True


class TestValidationIssue:
    def test_defaults(self):
        vi = ValidationIssue()
        assert vi.severity == "medium"
        assert vi.type == "missing_info"


class TestPipelineOutput:
    def test_minimal(self):
        out = PipelineOutput(
            request_id="REQ-001",
            processed_at="2026-03-19T12:00:00Z",
        )
        assert out.status == "processed"
        assert out.recommendation.status == "cannot_proceed"

    def test_serialization(self):
        out = PipelineOutput(
            request_id="REQ-001",
            processed_at="2026-03-19T12:00:00Z",
            recommendation=RecommendationOutput(
                status="proceed",
                reason="All clear",
                confidence_score=95,
            ),
        )
        d = out.model_dump()
        assert d["recommendation"]["status"] == "proceed"
        assert d["recommendation"]["confidence_score"] == 95


class TestEscalationData:
    def test_defaults(self):
        e = EscalationData()
        assert e.blocking is True
        assert e.rule_id == ""

    def test_from_dict(self):
        e = EscalationData.model_validate({
            "rule_id": "ER-001",
            "trigger": "Missing info",
            "escalate_to": "Requester",
            "blocking": True,
        })
        assert e.rule_id == "ER-001"
