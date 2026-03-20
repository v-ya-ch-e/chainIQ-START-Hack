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
                    risk_score=80,
                ),
            ],
        )
        result = await check_compliance(
            fetch_result, filter_result, mock_org_client, pipeline_logger
        )
        assert len(result.excluded) == 1
        assert "risk" in result.excluded[0].reason.lower()

    @pytest.mark.asyncio
    async def test_moderate_risk_non_preferred_not_excluded(
        self, mock_org_client, pipeline_logger
    ):
        """Non-preferred supplier with risk_score=50 should NOT be excluded (threshold=70)."""
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-MODRISK",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                delivery_countries=["DE"],
            ),
        )
        filter_result = FilterResult(
            enriched_suppliers=[
                EnrichedSupplier(
                    supplier_id="SUP-MODRISK",
                    supplier_name="Moderate Risk Corp",
                    preferred_supplier=False,
                    risk_score=50,
                ),
            ],
        )
        result = await check_compliance(
            fetch_result, filter_result, mock_org_client, pipeline_logger
        )
        assert len(result.compliant) == 1

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
    async def test_escalation_produces_results(
        self, sample_fetch_result, sample_validation_result,
        sample_compliance_result, sample_rank_result, pipeline_logger
    ):
        result = await compute_escalations(
            sample_fetch_result, sample_validation_result,
            sample_compliance_result, sample_rank_result, pipeline_logger
        )
        assert isinstance(result.escalations, list)

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
        assert result.confidence_score < 100

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

    def test_confidence_score_blocking_applies_heavy_penalty(self):
        escalations = [MagicMock(blocking=True)]
        score = _compute_confidence(escalations, [], [])
        assert score == 75  # 100 - 25 for 1 blocking

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

    def test_confidence_multiple_blocking_escalations(self):
        """Multiple blocking escalations apply 25 points each, not immediate zero."""
        escalations = [MagicMock(blocking=True), MagicMock(blocking=True)]
        score = _compute_confidence(escalations, [], [])
        assert score == 50  # 100 - 2*25

    def test_confidence_four_blocking_hits_zero(self):
        escalations = [MagicMock(blocking=True)] * 4
        score = _compute_confidence(escalations, [], [])
        assert score == 0


# ── Bug fix regression tests ──────────────────────────────────────


class TestBugFixRegressions:
    """Regression tests for all bugs identified in the code review."""

    @pytest.mark.asyncio
    async def test_er001_fires_for_missing_budget_not_insufficient(self, pipeline_logger):
        """Bug 2: ER-001 should fire for missing info (null budget), not budget insufficiency."""
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-BUG2",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                budget_amount=None,
                quantity=100,
            ),
        )
        val_result = ValidationResult(
            completeness=True,
            issues=[],
            request_interpretation=RequestInterpretation(category_l1="IT", category_l2="Laptops"),
        )
        compliance_result = ComplianceResult(
            compliant=[EnrichedSupplier(supplier_id="S1", supplier_name="A")],
        )
        rank_result = RankResult(
            ranked_suppliers=[RankedSupplier(
                supplier_id="S1", supplier_name="A",
                total_price=5000, true_cost=6000,
            )],
        )
        result = await compute_escalations(
            fetch_result, val_result, compliance_result, rank_result, pipeline_logger
        )
        er001 = [e for e in result.escalations if e.rule == "ER-001"]
        assert len(er001) == 1
        assert "missing" in er001[0].trigger.lower() or "Missing" in er001[0].trigger

    @pytest.mark.asyncio
    async def test_er001_does_not_fire_when_budget_present(self, pipeline_logger):
        """Bug 2: ER-001 should NOT fire when budget is present, even if insufficient."""
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-BUG2B",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                budget_amount=100,
                quantity=100,
            ),
        )
        val_result = ValidationResult(
            completeness=True,
            issues=[ValidationIssue(type="budget_insufficient", severity="critical")],
            request_interpretation=RequestInterpretation(),
        )
        compliance_result = ComplianceResult(
            compliant=[EnrichedSupplier(supplier_id="S1", supplier_name="A")],
        )
        rank_result = RankResult(
            ranked_suppliers=[RankedSupplier(
                supplier_id="S1", supplier_name="A",
                total_price=5000, true_cost=6000,
            )],
        )
        result = await compute_escalations(
            fetch_result, val_result, compliance_result, rank_result, pipeline_logger
        )
        er001 = [e for e in result.escalations if e.rule == "ER-001"]
        assert len(er001) == 0

    @pytest.mark.asyncio
    async def test_er009_is_non_blocking(self, pipeline_logger):
        """Bug 1: ER-009 must be non-blocking to avoid 100% cannot_proceed rate."""
        from app.pipeline.rule_engine import RuleEngine

        engine = RuleEngine()
        er009_rule = {
            "rule_id": "ER-009",
            "rule_name": "Contradictory request content",
            "eval_type": "compare",
            "eval_config": {
                "left_field": "has_contradictions",
                "operator": "==",
                "right_constant": False,
                "condition": None,
            },
            "action_on_fail": "escalate",
            "severity": "medium",
            "is_blocking": False,
            "escalation_target": "Procurement Manager",
            "fail_message_template": "Request contains contradictions",
            "is_active": True,
            "priority": 80,
            "version": 1,
        }
        ctx = {"has_contradictions": True}
        results = await engine.evaluate_rules([er009_rule], ctx)
        assert results[0].result == "failed"
        assert results[0].is_blocking is False

    @pytest.mark.asyncio
    async def test_er010_is_non_blocking(self, pipeline_logger):
        """Bug 7: ER-010 must be non-blocking."""
        from app.pipeline.rule_engine import RuleEngine

        engine = RuleEngine()
        er010_rule = {
            "rule_id": "ER-010",
            "rule_name": "Lead time infeasible",
            "eval_type": "compare",
            "eval_config": {
                "left_field": "has_lead_time_issue",
                "operator": "==",
                "right_constant": False,
                "condition": None,
            },
            "action_on_fail": "escalate",
            "severity": "high",
            "is_blocking": False,
            "escalation_target": "Head of Category",
            "is_active": True,
            "priority": 85,
            "version": 1,
        }
        ctx = {"has_lead_time_issue": True}
        results = await engine.evaluate_rules([er010_rule], ctx)
        assert results[0].result == "failed"
        assert results[0].is_blocking is False

    @pytest.mark.asyncio
    async def test_er004_only_for_no_compliant_suppliers(self, pipeline_logger):
        """Bug 9: ER-004 must only fire for no compliant suppliers, not lead time."""
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-BUG9",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                budget_amount=100000,
                quantity=100,
            ),
        )
        val_result = ValidationResult(
            completeness=True,
            issues=[ValidationIssue(type="lead_time_infeasible", severity="high",
                                    description="Lead time infeasible")],
            request_interpretation=RequestInterpretation(
                required_by_date="2026-03-20", days_until_required=1,
            ),
        )
        compliance_result = ComplianceResult(
            compliant=[EnrichedSupplier(supplier_id="S1", supplier_name="A")],
        )
        rank_result = RankResult(
            ranked_suppliers=[RankedSupplier(
                supplier_id="S1", supplier_name="A",
                total_price=50000, true_cost=60000,
                expedited_lead_time_days=20,
            )],
        )
        result = await compute_escalations(
            fetch_result, val_result, compliance_result, rank_result, pipeline_logger
        )
        er004 = [e for e in result.escalations if e.rule == "ER-004"]
        assert len(er004) == 0, "ER-004 should NOT fire for lead time issues"
        er010 = [e for e in result.escalations if e.rule == "ER-010"]
        assert len(er010) == 1, "ER-010 should fire for lead time issues"
        assert er010[0].blocking is False

    @pytest.mark.asyncio
    async def test_has_contradictions_excludes_policy_conflict(self, pipeline_logger):
        """Bug 12: has_contradictions should only flag 'contradictory', not 'policy_conflict'."""
        from app.pipeline.steps.escalate import _build_escalation_context

        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-BUG12",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                budget_amount=50000,
                quantity=100,
            ),
        )
        val_result = ValidationResult(
            completeness=True,
            issues=[
                ValidationIssue(type="policy_conflict", severity="high",
                                description="Policy conflict"),
            ],
            request_interpretation=RequestInterpretation(),
        )
        compliance_result = ComplianceResult(
            compliant=[EnrichedSupplier(supplier_id="S1", supplier_name="A")],
        )
        rank_result = RankResult(
            ranked_suppliers=[RankedSupplier(
                supplier_id="S1", supplier_name="A",
                total_price=40000, true_cost=50000,
            )],
        )
        ctx = _build_escalation_context(
            fetch_result, val_result, compliance_result, rank_result,
            budget=50000.0, quantity=100, currency="EUR",
        )
        assert ctx["has_contradictions"] is False, \
            "policy_conflict should NOT set has_contradictions"

    def test_single_supplier_capacity_risk_computed(self):
        """Bug 6: single_supplier_capacity_risk should be True when only 1 supplier meets qty."""
        from app.pipeline.steps.escalate import _build_escalation_context

        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-CAP-RISK",
                category_l1="IT",
                category_l2="Servers",
                currency="EUR",
                budget_amount=100000,
                quantity=500,
            ),
        )
        val_result = ValidationResult(
            completeness=True, issues=[],
            request_interpretation=RequestInterpretation(),
        )
        compliance_result = ComplianceResult(
            compliant=[
                EnrichedSupplier(supplier_id="S1", supplier_name="A", capacity_per_month=600),
                EnrichedSupplier(supplier_id="S2", supplier_name="B", capacity_per_month=200),
            ],
        )
        rank_result = RankResult(ranked_suppliers=[])

        ctx = _build_escalation_context(
            fetch_result, val_result, compliance_result, rank_result,
            budget=100000.0, quantity=500, currency="EUR",
        )
        assert ctx["single_supplier_capacity_risk"] is True

    def test_no_single_supplier_capacity_risk_when_multiple(self):
        from app.pipeline.steps.escalate import _build_escalation_context

        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-NOCAPRISK",
                category_l1="IT",
                category_l2="Servers",
                currency="EUR",
                budget_amount=100000,
                quantity=500,
            ),
        )
        val_result = ValidationResult(
            completeness=True, issues=[],
            request_interpretation=RequestInterpretation(),
        )
        compliance_result = ComplianceResult(
            compliant=[
                EnrichedSupplier(supplier_id="S1", supplier_name="A", capacity_per_month=600),
                EnrichedSupplier(supplier_id="S2", supplier_name="B", capacity_per_month=800),
            ],
        )
        rank_result = RankResult(ranked_suppliers=[])

        ctx = _build_escalation_context(
            fetch_result, val_result, compliance_result, rank_result,
            budget=100000.0, quantity=500, currency="EUR",
        )
        assert ctx["single_supplier_capacity_risk"] is False

    @pytest.mark.asyncio
    async def test_er007_fires_only_for_influencer_campaigns(self):
        """Bug 5: ER-007 should only escalate when category IS Influencer Campaign Management."""
        from app.pipeline.rule_engine import RuleEngine

        engine = RuleEngine()
        er007_rule = {
            "rule_id": "ER-007",
            "rule_name": "Brand safety concern",
            "eval_type": "compare",
            "eval_config": {
                "left_field": "category_l2",
                "operator": "!=",
                "right_constant": "Influencer Campaign Management",
                "condition": None,
            },
            "action_on_fail": "escalate",
            "severity": "high",
            "is_blocking": False,
            "escalation_target": "Marketing Governance Lead",
            "is_active": True,
            "priority": 60,
            "version": 1,
        }

        influencer_ctx = {"category_l2": "Influencer Campaign Management"}
        results = await engine.evaluate_rules([er007_rule], influencer_ctx)
        assert results[0].result == "failed", "ER-007 should fire for Influencer Campaign"
        assert results[0].action == "escalate"

        laptops_ctx = {"category_l2": "Laptops"}
        results = await engine.evaluate_rules([er007_rule], laptops_ctx)
        assert results[0].result == "passed", "ER-007 should NOT fire for Laptops"

    @pytest.mark.asyncio
    async def test_er005_target_is_security_compliance(self):
        """Bug 4: ER-005 should escalate to Security/Compliance, not Data Protection Officer."""
        from app.pipeline.rule_engine import RuleEngine

        engine = RuleEngine()
        er005_rule = {
            "rule_id": "ER-005",
            "rule_name": "Data residency unsatisfiable",
            "eval_type": "compare",
            "eval_config": {
                "left_field": "has_residency_supplier",
                "operator": "==",
                "right_constant": True,
                "condition": {"field": "data_residency_constraint", "operator": "==", "value": True},
            },
            "action_on_fail": "escalate",
            "severity": "critical",
            "is_blocking": True,
            "escalation_target": "Security/Compliance",
            "is_active": True,
            "priority": 50,
            "version": 1,
        }
        ctx = {
            "data_residency_constraint": True,
            "has_residency_supplier": False,
        }
        results = await engine.evaluate_rules([er005_rule], ctx)
        assert results[0].result == "failed"
        assert results[0].escalation_target == "Security/Compliance"

    @pytest.mark.asyncio
    async def test_er001_required_eval_type_fires_for_null_budget(self):
        """Bug 2: ER-001 as 'required' eval_type fires for null budget_amount."""
        from app.pipeline.rule_engine import RuleEngine

        engine = RuleEngine()
        er001_rule = {
            "rule_id": "ER-001",
            "rule_name": "Missing required info",
            "eval_type": "required",
            "eval_config": {
                "fields": [
                    {"name": "budget_amount", "severity": "critical"},
                    {"name": "quantity", "severity": "critical"},
                ]
            },
            "action_on_fail": "escalate",
            "severity": "critical",
            "is_blocking": True,
            "escalation_target": "Requester Clarification",
            "is_active": True,
            "priority": 10,
            "version": 1,
        }
        ctx = {"budget_amount": None, "quantity": 100}
        results = await engine.evaluate_rules([er001_rule], ctx)
        assert results[0].result == "failed"
        assert "budget_amount" in results[0].actual_values.get("missing", [])

        ctx_ok = {"budget_amount": 50000, "quantity": 100}
        results = await engine.evaluate_rules([er001_rule], ctx_ok)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_fallback_lead_time_uses_er010_not_er004(self, pipeline_logger):
        """Bug 9: Fallback path should use ER-010 for lead time, not ER-004."""
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-FALLBACK-LT",
                category_l1="IT",
                category_l2="Laptops",
                currency="EUR",
                budget_amount=100000,
                quantity=100,
            ),
        )
        val_result = ValidationResult(
            completeness=True,
            issues=[ValidationIssue(
                type="lead_time_infeasible", severity="high",
                description="Lead time infeasible",
            )],
            request_interpretation=RequestInterpretation(
                required_by_date="2026-03-20", days_until_required=1,
            ),
        )
        compliance_result = ComplianceResult(
            compliant=[EnrichedSupplier(supplier_id="S1", supplier_name="A")],
        )
        rank_result = RankResult(
            ranked_suppliers=[RankedSupplier(
                supplier_id="S1", supplier_name="A",
                total_price=50000, true_cost=60000,
                expedited_lead_time_days=20,
            )],
        )
        result = await compute_escalations(
            fetch_result, val_result, compliance_result, rank_result, pipeline_logger
        )
        rules = [e.rule for e in result.escalations]
        assert "ER-004" not in rules
        assert "ER-010" in rules
        er010 = next(e for e in result.escalations if e.rule == "ER-010")
        assert er010.blocking is False

    @pytest.mark.asyncio
    async def test_fallback_er005_targets_security_compliance(self, pipeline_logger):
        """Bug 4: Fallback path should escalate ER-005 to Security/Compliance."""
        fetch_result = FetchResult(
            request=RequestData(
                request_id="REQ-FALLBACK-DR",
                category_l1="IT",
                category_l2="Cloud Storage",
                currency="EUR",
                data_residency_constraint=True,
                delivery_countries=["DE"],
            ),
        )
        val_result = ValidationResult(
            completeness=True, issues=[],
            request_interpretation=RequestInterpretation(),
        )
        compliance_result = ComplianceResult(
            compliant=[
                EnrichedSupplier(
                    supplier_id="S1", supplier_name="A",
                    data_residency_supported=False,
                ),
            ],
        )
        rank_result = RankResult(ranked_suppliers=[])
        result = await compute_escalations(
            fetch_result, val_result, compliance_result, rank_result, pipeline_logger
        )
        er005 = [e for e in result.escalations if e.rule == "ER-005"]
        assert len(er005) == 1
        assert er005[0].escalate_to == "Security/Compliance"
