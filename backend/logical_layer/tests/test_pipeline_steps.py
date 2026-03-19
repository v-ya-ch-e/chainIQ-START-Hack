"""Tests for individual pipeline steps."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.common import (
    PricingData,
    RequestData,
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
    ValidationIssue,
    ValidationResult,
    RequestInterpretation,
)
from app.pipeline.logger import PipelineLogger
from app.pipeline.steps.fetch import fetch_overview
from app.pipeline.steps.validate import validate_request
from app.pipeline.steps.filter import filter_suppliers, _match_pricing_tier
from app.pipeline.steps.comply import check_compliance
from app.pipeline.steps.rank import rank_suppliers
from app.pipeline.steps.escalate import compute_escalations
from app.pipeline.steps.recommend import generate_recommendation, _compute_confidence


# ── Step 1: Fetch ──────────────────────────────────────────────────


class TestFetch:
    @pytest.mark.asyncio
    async def test_fetch_overview_success(self, mock_org_client, pipeline_logger):
        result = await fetch_overview("REQ-000004", mock_org_client, pipeline_logger)

        assert result.request.request_id == "REQ-000004"
        assert len(result.compliant_suppliers) == 3
        assert len(result.pricing) == 3
        assert result.approval_tier is not None
        assert result.approval_tier.threshold_id == "AT-002"
        assert len(result.historical_awards) == 1

    @pytest.mark.asyncio
    async def test_fetch_overview_propagates_error(self, mock_org_client, pipeline_logger):
        mock_org_client.get_request_overview = AsyncMock(
            side_effect=Exception("Org Layer unreachable")
        )
        with pytest.raises(Exception, match="Org Layer unreachable"):
            await fetch_overview("REQ-INVALID", mock_org_client, pipeline_logger)


# ── Step 2: Validate ──────────────────────────────────────────────


class TestValidate:
    @pytest.mark.asyncio
    async def test_validate_complete_request(self, sample_fetch_result, pipeline_logger):
        result = await validate_request(sample_fetch_result, None, pipeline_logger)
        assert result.completeness is True
        assert result.request_interpretation.category_l1 == "IT"
        assert result.request_interpretation.quantity == 240

    @pytest.mark.asyncio
    async def test_validate_missing_category(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-MISSING",
                category_l1=None,
                category_l2=None,
                currency="EUR",
            ),
        )
        result = await validate_request(fetch_result, None, pipeline_logger)
        assert result.completeness is False
        critical_issues = [i for i in result.issues if i.severity == "critical"]
        assert len(critical_issues) >= 2
        types = {i.type for i in critical_issues}
        assert "missing_info" in types

    @pytest.mark.asyncio
    async def test_validate_missing_currency(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-NOCUR",
                category_l1="IT",
                category_l2="Laptops",
                currency=None,
            ),
        )
        result = await validate_request(fetch_result, None, pipeline_logger)
        assert result.completeness is False
        fields = [i.field for i in result.issues if i.severity == "critical"]
        assert "currency" in fields

    @pytest.mark.asyncio
    async def test_validate_null_budget_flagged(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-NOBUDGET",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                budget_amount=None,
            ),
        )
        result = await validate_request(fetch_result, None, pipeline_logger)
        assert result.completeness is True
        budget_issues = [i for i in result.issues if i.field == "budget_amount"]
        assert len(budget_issues) == 1
        assert budget_issues[0].severity == "high"

    @pytest.mark.asyncio
    async def test_validate_null_quantity_flagged(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-NOQTY",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                quantity=None,
            ),
        )
        result = await validate_request(fetch_result, None, pipeline_logger)
        qty_issues = [i for i in result.issues if i.field == "quantity"]
        assert len(qty_issues) == 1

    @pytest.mark.asyncio
    async def test_validate_budget_insufficient(self, sample_fetch_result, pipeline_logger):
        result = await validate_request(sample_fetch_result, None, pipeline_logger)
        budget_issues = [i for i in result.issues if i.type == "budget_insufficient"]
        assert len(budget_issues) == 1

    @pytest.mark.asyncio
    async def test_validate_no_delivery_countries(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-NODC",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                delivery_countries=[],
                country=None,
            ),
        )
        result = await validate_request(fetch_result, None, pipeline_logger)
        dc_issues = [i for i in result.issues if i.field == "delivery_countries"]
        assert len(dc_issues) == 1


# ── Step 3: Filter ─────────────────────────────────────────────────


class TestFilter:
    @pytest.mark.asyncio
    async def test_filter_enriches_suppliers(self, sample_fetch_result, pipeline_logger):
        result = await filter_suppliers(sample_fetch_result, pipeline_logger)
        assert len(result.enriched_suppliers) == 3
        for es in result.enriched_suppliers:
            assert es.has_pricing is True
            assert es.unit_price is not None

    @pytest.mark.asyncio
    async def test_filter_no_pricing_for_supplier(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-NOPR",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                quantity=50,
            ),
            compliant_suppliers=[
                SupplierData(supplier_id="SUP-NOPR", supplier_name="No Pricing Co"),
            ],
            pricing=[],
        )
        result = await filter_suppliers(fetch_result, pipeline_logger)
        assert len(result.enriched_suppliers) == 1
        assert result.enriched_suppliers[0].has_pricing is False
        assert "SUP-NOPR" in result.suppliers_without_pricing

    def test_match_pricing_tier_exact(self):
        tier = MagicMock(min_quantity=100, max_quantity=499)
        result = _match_pricing_tier([tier], 240)
        assert result is tier

    def test_match_pricing_tier_no_match(self):
        tier = MagicMock(min_quantity=100, max_quantity=499)
        result = _match_pricing_tier([tier], 50)
        assert result is None

    def test_match_pricing_tier_null_quantity(self):
        tier = MagicMock(min_quantity=100, max_quantity=499)
        result = _match_pricing_tier([tier], None)
        assert result is None

    def test_match_pricing_tier_empty_tiers(self):
        result = _match_pricing_tier([], 100)
        assert result is None


# ── Step 4: Compliance ─────────────────────────────────────────────


class TestCompliance:
    @pytest.mark.asyncio
    async def test_all_pass(
        self, sample_fetch_result, sample_filter_result, mock_org_client, pipeline_logger
    ):
        result = await check_compliance(
            sample_fetch_result, sample_filter_result, mock_org_client, pipeline_logger
        )
        assert len(result.compliant) == 3
        assert len(result.excluded) == 0

    @pytest.mark.asyncio
    async def test_data_residency_exclusion(
        self, mock_org_client, pipeline_logger
    ):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-DR",
                category_l1="IT",
                category_l2="Cloud Storage",
                currency="EUR",
                data_residency_constraint=True,
                delivery_countries=["DE"],
            ),
        )
        filter_result = FilterResult(
            enriched_suppliers=[
                EnrichedSupplier(
                    supplier_id="SUP-NODR",
                    supplier_name="No Residency Corp",
                    data_residency_supported=False,
                ),
            ],
        )
        result = await check_compliance(
            fetch_result, filter_result, mock_org_client, pipeline_logger
        )
        assert len(result.excluded) == 1
        assert "residency" in result.excluded[0].reason.lower()

    @pytest.mark.asyncio
    async def test_capacity_exclusion(
        self, mock_org_client, pipeline_logger
    ):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-CAP",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                quantity=50000,
                delivery_countries=["DE"],
            ),
        )
        filter_result = FilterResult(
            enriched_suppliers=[
                EnrichedSupplier(
                    supplier_id="SUP-SMALL",
                    supplier_name="Small Supplier",
                    capacity_per_month=1000,
                ),
            ],
        )
        result = await check_compliance(
            fetch_result, filter_result, mock_org_client, pipeline_logger
        )
        assert len(result.excluded) == 1
        assert "capacity" in result.excluded[0].reason.lower()

    @pytest.mark.asyncio
    async def test_risk_exclusion_non_preferred(
        self, mock_org_client, pipeline_logger
    ):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-RISK",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                delivery_countries=["DE"],
            ),
        )
        filter_result = FilterResult(
            enriched_suppliers=[
                EnrichedSupplier(
                    supplier_id="SUP-RISKY",
                    supplier_name="Risky Corp",
                    preferred_supplier=False,
                    risk_score=50,
                ),
            ],
        )
        result = await check_compliance(
            fetch_result, filter_result, mock_org_client, pipeline_logger
        )
        assert len(result.excluded) == 1
        assert "risk" in result.excluded[0].reason.lower()

    @pytest.mark.asyncio
    async def test_preferred_supplier_not_excluded_on_risk(
        self, mock_org_client, pipeline_logger
    ):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-PREFR",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                delivery_countries=["DE"],
            ),
        )
        filter_result = FilterResult(
            enriched_suppliers=[
                EnrichedSupplier(
                    supplier_id="SUP-PREFRISK",
                    supplier_name="Pref Risky Corp",
                    preferred_supplier=True,
                    risk_score=50,
                ),
            ],
        )
        result = await check_compliance(
            fetch_result, filter_result, mock_org_client, pipeline_logger
        )
        assert len(result.compliant) == 1

    @pytest.mark.asyncio
    async def test_restricted_supplier_excluded(
        self, mock_org_client, pipeline_logger
    ):
        mock_org_client.check_restricted = AsyncMock(return_value={
            "is_restricted": True,
            "restriction_reason": "Sanctioned in DE",
        })
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-REST",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                delivery_countries=["DE"],
            ),
        )
        filter_result = FilterResult(
            enriched_suppliers=[
                EnrichedSupplier(
                    supplier_id="SUP-REST",
                    supplier_name="Restricted Corp",
                ),
            ],
        )
        result = await check_compliance(
            fetch_result, filter_result, mock_org_client, pipeline_logger
        )
        assert len(result.excluded) == 1
        assert "restricted" in result.excluded[0].reason.lower()

    @pytest.mark.asyncio
    async def test_restriction_check_error_logged_not_fatal(
        self, mock_org_client, pipeline_logger
    ):
        mock_org_client.check_restricted = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-ERR",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                delivery_countries=["DE"],
            ),
        )
        filter_result = FilterResult(
            enriched_suppliers=[
                EnrichedSupplier(
                    supplier_id="SUP-ERR",
                    supplier_name="Error Corp",
                ),
            ],
        )
        result = await check_compliance(
            fetch_result, filter_result, mock_org_client, pipeline_logger
        )
        assert len(result.compliant) == 1


# ── Step 5: Rank ───────────────────────────────────────────────────


class TestRank:
    @pytest.mark.asyncio
    async def test_rank_by_true_cost(
        self, sample_fetch_result, sample_compliance_result, pipeline_logger
    ):
        result = await rank_suppliers(
            sample_fetch_result, sample_compliance_result, pipeline_logger
        )
        assert result.ranking_method == "true_cost"
        assert len(result.ranked_suppliers) == 3
        assert result.ranked_suppliers[0].rank == 1
        for i in range(len(result.ranked_suppliers) - 1):
            s1 = result.ranked_suppliers[i]
            s2 = result.ranked_suppliers[i + 1]
            if s1.true_cost is not None and s2.true_cost is not None:
                assert s1.true_cost <= s2.true_cost

    @pytest.mark.asyncio
    async def test_rank_by_quality_when_no_quantity(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-NOQTY",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                quantity=None,
            ),
        )
        compliance_result = ComplianceResult(
            compliant=[
                EnrichedSupplier(
                    supplier_id="SUP-A",
                    supplier_name="A",
                    quality_score=90,
                    risk_score=10,
                ),
                EnrichedSupplier(
                    supplier_id="SUP-B",
                    supplier_name="B",
                    quality_score=80,
                    risk_score=20,
                ),
            ],
        )
        result = await rank_suppliers(fetch_result, compliance_result, pipeline_logger)
        assert result.ranking_method == "quality_score"
        assert result.ranked_suppliers[0].supplier_id == "SUP-A"

    @pytest.mark.asyncio
    async def test_rank_detects_incumbent(
        self, sample_fetch_result, sample_compliance_result, pipeline_logger
    ):
        result = await rank_suppliers(
            sample_fetch_result, sample_compliance_result, pipeline_logger
        )
        bechtle = next(
            s for s in result.ranked_suppliers if s.supplier_id == "SUP-0007"
        )
        assert bechtle.incumbent is True

    @pytest.mark.asyncio
    async def test_rank_empty_suppliers(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-EMPTY",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
            ),
        )
        compliance_result = ComplianceResult(compliant=[], excluded=[])
        result = await rank_suppliers(fetch_result, compliance_result, pipeline_logger)
        assert len(result.ranked_suppliers) == 0


# ── Step 7: Escalations ───────────────────────────────────────────


class TestEscalations:
    @pytest.mark.asyncio
    async def test_budget_insufficient_escalation(
        self, sample_fetch_result, sample_validation_result,
        sample_compliance_result, sample_rank_result, pipeline_logger
    ):
        result = await compute_escalations(
            sample_fetch_result, sample_validation_result,
            sample_compliance_result, sample_rank_result, pipeline_logger
        )
        rules = [e.rule for e in result.escalations]
        assert "ER-001" in rules

    @pytest.mark.asyncio
    async def test_no_escalations_for_clean_request(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-CLEAN",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                budget_amount=100000,
                quantity=100,
            ),
        )
        val_result = ValidationResult(
            completeness=True,
            issues=[],
            request_interpretation=RequestInterpretation(
                category_l1="IT", category_l2="Laptops",
            ),
        )
        compliance_result = ComplianceResult(
            compliant=[EnrichedSupplier(supplier_id="S1", supplier_name="A")],
        )
        rank_result = RankResult(
            ranked_suppliers=[RankedSupplier(
                supplier_id="S1", supplier_name="A",
                total_price=50000.0, true_cost=60000.0,
            )],
        )
        result = await compute_escalations(
            fetch_result, val_result, compliance_result, rank_result, pipeline_logger
        )
        assert result.has_blocking is False

    @pytest.mark.asyncio
    async def test_no_compliant_suppliers_escalation(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-NOSUP",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
            ),
            compliant_suppliers=[
                SupplierData(supplier_id="SUP-1", supplier_name="A"),
            ],
        )
        val_result = ValidationResult(
            completeness=True,
            request_interpretation=RequestInterpretation(),
        )
        compliance_result = ComplianceResult(
            compliant=[],
            excluded=[ExcludedSupplier(supplier_id="SUP-1", supplier_name="A", reason="risk")],
        )
        rank_result = RankResult(ranked_suppliers=[])

        result = await compute_escalations(
            fetch_result, val_result, compliance_result, rank_result, pipeline_logger
        )
        rules = [e.rule for e in result.escalations]
        assert "ER-004" in rules

    @pytest.mark.asyncio
    async def test_preferred_restricted_escalation(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-PREF",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                preferred_supplier_mentioned="Restricted Corp",
            ),
        )
        val_result = ValidationResult(
            completeness=True,
            request_interpretation=RequestInterpretation(),
        )
        compliance_result = ComplianceResult(
            compliant=[],
            excluded=[
                ExcludedSupplier(
                    supplier_id="SUP-R",
                    supplier_name="Restricted Corp",
                    reason="Restricted: Sanctioned",
                ),
            ],
        )
        rank_result = RankResult(ranked_suppliers=[])

        result = await compute_escalations(
            fetch_result, val_result, compliance_result, rank_result, pipeline_logger
        )
        rules = [e.rule for e in result.escalations]
        assert "ER-002" in rules

    @pytest.mark.asyncio
    async def test_escalation_deduplication(self, pipeline_logger):
        from app.models.common import EscalationData as ED
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-DEDUP",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                budget_amount=100,
                quantity=10,
            ),
            org_escalations=[
                ED(rule_id="ER-001", trigger="short", escalate_to="Manager", blocking=True),
            ],
        )
        val_result = ValidationResult(
            completeness=True,
            issues=[
                ValidationIssue(type="budget_insufficient", severity="critical"),
            ],
            request_interpretation=RequestInterpretation(),
        )
        compliance_result = ComplianceResult(
            compliant=[EnrichedSupplier(supplier_id="S1", supplier_name="A")],
        )
        rank_result = RankResult(
            ranked_suppliers=[RankedSupplier(
                supplier_id="S1", supplier_name="A",
                total_price=500, true_cost=600,
            )],
        )
        result = await compute_escalations(
            fetch_result, val_result, compliance_result, rank_result, pipeline_logger
        )
        er001_count = sum(1 for e in result.escalations if e.rule == "ER-001")
        assert er001_count == 1


# ── Step 8: Recommendation ────────────────────────────────────────


class TestRecommendation:
    @pytest.mark.asyncio
    async def test_cannot_proceed_with_blocking(
        self, sample_fetch_result, sample_validation_result,
        sample_rank_result, sample_escalation_result, pipeline_logger
    ):
        result = await generate_recommendation(
            sample_fetch_result, sample_validation_result,
            sample_rank_result, sample_escalation_result,
            None, pipeline_logger,
        )
        assert result.status == "cannot_proceed"
        assert result.confidence_score == 0

    @pytest.mark.asyncio
    async def test_proceed_no_escalations(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-GO",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                budget_amount=100000,
            ),
        )
        val_result = ValidationResult(
            completeness=True,
            request_interpretation=RequestInterpretation(
                category_l1="IT", category_l2="Laptops",
            ),
        )
        rank_result = RankResult(
            ranked_suppliers=[
                RankedSupplier(
                    supplier_id="SUP-1", supplier_name="Best Corp",
                    total_price=50000, true_cost=60000,
                    quality_score=90, risk_score=10,
                ),
            ],
        )
        esc_result = EscalationResult(
            escalations=[], has_blocking=False,
            blocking_count=0, non_blocking_count=0,
        )
        result = await generate_recommendation(
            fetch_result, val_result, rank_result, esc_result, None, pipeline_logger
        )
        assert result.status == "proceed"
        assert result.confidence_score > 0
        assert result.preferred_supplier_if_resolved == "Best Corp"

    @pytest.mark.asyncio
    async def test_proceed_with_conditions(self, pipeline_logger):
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-COND",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
            ),
        )
        val_result = ValidationResult(
            completeness=True,
            request_interpretation=RequestInterpretation(),
        )
        rank_result = RankResult(
            ranked_suppliers=[
                RankedSupplier(
                    supplier_id="S1", supplier_name="A",
                    total_price=5000, true_cost=6000,
                    quality_score=85, risk_score=15,
                ),
            ],
        )
        esc_result = EscalationResult(
            escalations=[
                Escalation(rule="ER-006", trigger="Capacity risk",
                           escalate_to="PM", blocking=False),
            ],
            has_blocking=False, blocking_count=0, non_blocking_count=1,
        )
        result = await generate_recommendation(
            fetch_result, val_result, rank_result, esc_result, None, pipeline_logger
        )
        assert result.status == "proceed_with_conditions"

    def test_confidence_score_blocking_is_zero(self):
        escalations = [MagicMock(blocking=True)]
        assert _compute_confidence(escalations, [], []) == 0

    def test_confidence_score_no_issues(self):
        score = _compute_confidence([], [], [
            MagicMock(preferred=True, true_cost=100),
        ])
        assert score > 90

    def test_confidence_penalized_by_issues(self):
        issues = [MagicMock(severity="critical"), MagicMock(severity="high")]
        score = _compute_confidence([], issues, [])
        assert score < 100

    def test_confidence_bonus_for_price_gap(self):
        suppliers = [
            MagicMock(preferred=False, true_cost=100),
            MagicMock(preferred=False, true_cost=200),
        ]
        score = _compute_confidence([], [], suppliers)
        assert score >= 100
