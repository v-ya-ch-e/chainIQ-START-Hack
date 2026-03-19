from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models.historical import HistoricalAward
from app.models.policies import (
    ApprovalThreshold,
    ApprovalThresholdDeviationApprover,
    ApprovalThresholdManager,
    CategoryRule,
    GeographyRule,
    GeographyRuleAppliesToCategory,
    GeographyRuleCountry,
    PreferredSupplierPolicy,
    PreferredSupplierRegionScope,
    RestrictedSupplierPolicy,
    RestrictedSupplierScope,
)
from app.models.reference import (
    Category,
    PricingTier,
    Supplier,
    SupplierCategory,
    SupplierServiceRegion,
)
from app.models.requests import Request, RequestDeliveryCountry, RequestScenarioTag
from app.schemas.analytics import (
    ApplicableRulesOut,
    ApprovalTierOut,
    CompliantSupplierOut,
    PreferredCheckOut,
    PricingLookupOut,
    RequestOverviewOut,
    RestrictionCheckOut,
    SpendByCategoryOut,
    SpendBySupplierOut,
    SupplierWinRateOut,
)

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])

COUNTRY_TO_REGION = {
    "DE": "EU", "FR": "EU", "NL": "EU", "BE": "EU", "AT": "EU",
    "IT": "EU", "ES": "EU", "PL": "EU", "UK": "EU",
    "CH": "CH",
    "US": "Americas", "CA": "Americas", "BR": "Americas", "MX": "Americas",
    "SG": "APAC", "AU": "APAC", "IN": "APAC", "JP": "APAC",
    "UAE": "MEA", "ZA": "MEA",
}


@router.get("/compliant-suppliers", response_model=list[CompliantSupplierOut])
def find_compliant_suppliers(
    category_l1: str,
    category_l2: str,
    delivery_country: str,
    db: Session = Depends(get_db),
):
    """Find all non-restricted suppliers that serve the given category and delivery country."""
    restricted_sub = (
        db.query(RestrictedSupplierPolicy.supplier_id)
        .join(RestrictedSupplierScope)
        .filter(
            RestrictedSupplierPolicy.category_l1 == category_l1,
            RestrictedSupplierPolicy.category_l2 == category_l2,
            or_(
                RestrictedSupplierScope.scope_value == "all",
                RestrictedSupplierScope.scope_value == delivery_country,
            ),
        )
        .subquery()
    )

    rows = (
        db.query(
            Supplier.supplier_id,
            Supplier.supplier_name,
            Supplier.country_hq,
            Supplier.currency,
            Supplier.capacity_per_month,
            SupplierCategory.quality_score,
            SupplierCategory.risk_score,
            SupplierCategory.esg_score,
            SupplierCategory.preferred_supplier,
            SupplierCategory.data_residency_supported,
        )
        .join(SupplierCategory, Supplier.supplier_id == SupplierCategory.supplier_id)
        .join(Category, SupplierCategory.category_id == Category.id)
        .join(
            SupplierServiceRegion,
            Supplier.supplier_id == SupplierServiceRegion.supplier_id,
        )
        .filter(
            Category.category_l1 == category_l1,
            Category.category_l2 == category_l2,
            SupplierServiceRegion.country_code == delivery_country,
            ~Supplier.supplier_id.in_(db.query(restricted_sub)),
        )
        .all()
    )

    return [
        CompliantSupplierOut(
            supplier_id=r.supplier_id,
            supplier_name=r.supplier_name,
            country_hq=r.country_hq,
            currency=r.currency,
            quality_score=r.quality_score,
            risk_score=r.risk_score,
            esg_score=r.esg_score,
            preferred_supplier=r.preferred_supplier,
            data_residency_supported=r.data_residency_supported,
            capacity_per_month=r.capacity_per_month,
        )
        for r in rows
    ]


@router.get("/pricing-lookup", response_model=list[PricingLookupOut])
def pricing_lookup(
    supplier_id: str,
    category_l1: str,
    category_l2: str,
    region: str,
    quantity: int,
    db: Session = Depends(get_db),
):
    """Look up the correct pricing tier for a supplier+category+region+quantity."""
    rows = (
        db.query(PricingTier, Supplier.supplier_name)
        .join(Category, PricingTier.category_id == Category.id)
        .join(Supplier, PricingTier.supplier_id == Supplier.supplier_id)
        .filter(
            PricingTier.supplier_id == supplier_id,
            Category.category_l1 == category_l1,
            Category.category_l2 == category_l2,
            PricingTier.region == region,
            PricingTier.min_quantity <= quantity,
            PricingTier.max_quantity >= quantity,
        )
        .all()
    )

    return [
        PricingLookupOut(
            pricing_id=pt.pricing_id,
            supplier_id=pt.supplier_id,
            supplier_name=name,
            region=pt.region,
            currency=pt.currency,
            min_quantity=pt.min_quantity,
            max_quantity=pt.max_quantity,
            unit_price=pt.unit_price,
            expedited_unit_price=pt.expedited_unit_price,
            total_price=pt.unit_price * quantity,
            expedited_total_price=pt.expedited_unit_price * quantity,
            standard_lead_time_days=pt.standard_lead_time_days,
            expedited_lead_time_days=pt.expedited_lead_time_days,
            moq=pt.moq,
        )
        for pt, name in rows
    ]


@router.get("/approval-tier", response_model=ApprovalTierOut)
def get_approval_tier(
    currency: str,
    amount: Decimal,
    db: Session = Depends(get_db),
):
    """Determine the approval threshold tier for a given currency and amount."""
    t = (
        db.query(ApprovalThreshold)
        .options(
            joinedload(ApprovalThreshold.managers),
            joinedload(ApprovalThreshold.deviation_approvers),
        )
        .filter(
            ApprovalThreshold.currency == currency,
            ApprovalThreshold.min_amount <= amount,
            or_(
                ApprovalThreshold.max_amount.is_(None),
                ApprovalThreshold.max_amount >= amount,
            ),
        )
        .first()
    )

    if not t:
        raise HTTPException(
            status_code=404,
            detail=f"No approval threshold found for {currency} {amount}",
        )

    return ApprovalTierOut(
        threshold_id=t.threshold_id,
        currency=t.currency,
        min_amount=t.min_amount,
        max_amount=t.max_amount,
        min_supplier_quotes=t.min_supplier_quotes,
        policy_note=t.policy_note,
        managers=[m.manager_role for m in t.managers],
        deviation_approvers=[d.approver_role for d in t.deviation_approvers],
    )


@router.get("/check-restricted", response_model=RestrictionCheckOut)
def check_restricted(
    supplier_id: str,
    category_l1: str,
    category_l2: str,
    delivery_country: str,
    db: Session = Depends(get_db),
):
    """Check if a supplier is restricted for the given category and delivery country."""
    rows = (
        db.query(RestrictedSupplierPolicy, RestrictedSupplierScope.scope_value)
        .join(RestrictedSupplierScope)
        .filter(
            RestrictedSupplierPolicy.supplier_id == supplier_id,
            RestrictedSupplierPolicy.category_l1 == category_l1,
            RestrictedSupplierPolicy.category_l2 == category_l2,
            or_(
                RestrictedSupplierScope.scope_value == "all",
                RestrictedSupplierScope.scope_value == delivery_country,
            ),
        )
        .all()
    )

    if not rows:
        return RestrictionCheckOut(supplier_id=supplier_id, is_restricted=False)

    policy = rows[0][0]
    return RestrictionCheckOut(
        supplier_id=supplier_id,
        is_restricted=True,
        restriction_reason=policy.restriction_reason,
        scope_values=[sv for _, sv in rows],
    )


@router.get("/check-preferred", response_model=PreferredCheckOut)
def check_preferred(
    supplier_id: str,
    category_l1: str,
    category_l2: str,
    region: str | None = None,
    db: Session = Depends(get_db),
):
    """Check if a supplier is preferred for the given category and region."""
    q = (
        db.query(PreferredSupplierPolicy)
        .options(joinedload(PreferredSupplierPolicy.region_scopes))
        .filter(
            PreferredSupplierPolicy.supplier_id == supplier_id,
            PreferredSupplierPolicy.category_l1 == category_l1,
            PreferredSupplierPolicy.category_l2 == category_l2,
        )
    )
    policies = q.all()

    for p in policies:
        scopes = [rs.region for rs in p.region_scopes]
        if not scopes or (region and region in scopes):
            return PreferredCheckOut(
                supplier_id=supplier_id,
                is_preferred=True,
                policy_note=p.policy_note,
                region_scopes=scopes if scopes else ["global"],
            )

    return PreferredCheckOut(supplier_id=supplier_id, is_preferred=False)


@router.get("/applicable-rules", response_model=ApplicableRulesOut)
def get_applicable_rules(
    category_l1: str,
    category_l2: str,
    delivery_country: str,
    db: Session = Depends(get_db),
):
    """Get all category and geography rules that apply for the given context."""
    cat_rules = (
        db.query(CategoryRule)
        .join(Category, CategoryRule.category_id == Category.id)
        .filter(
            Category.category_l1 == category_l1,
            Category.category_l2 == category_l2,
        )
        .all()
    )

    # Single-country rules
    single_geo = (
        db.query(GeographyRule)
        .filter(GeographyRule.country == delivery_country)
        .all()
    )

    # Region-level rules that apply to this country and category
    region_geo = (
        db.query(GeographyRule)
        .join(GeographyRuleCountry)
        .join(GeographyRuleAppliesToCategory)
        .filter(
            GeographyRuleCountry.country_code == delivery_country,
            GeographyRuleAppliesToCategory.category_l1 == category_l1,
        )
        .all()
    )

    return ApplicableRulesOut(
        category_rules=[
            {
                "rule_id": r.rule_id,
                "category_id": r.category_id,
                "rule_type": r.rule_type,
                "rule_text": r.rule_text,
            }
            for r in cat_rules
        ],
        geography_rules=[
            {
                "rule_id": r.rule_id,
                "country": r.country,
                "region": r.region,
                "rule_type": r.rule_type,
                "rule_text": r.rule_text,
            }
            for r in single_geo + region_geo
        ],
    )


@router.get("/request-overview/{request_id}", response_model=RequestOverviewOut)
def get_request_overview(request_id: str, db: Session = Depends(get_db)):
    """
    Comprehensive read-only evaluation of a request: details, compliant suppliers
    with pricing, applicable rules, approval tier, and historical awards.

    For multi-country deliveries, suppliers must serve ALL delivery countries,
    restrictions are checked against ALL countries, pricing is looked up for
    each unique pricing region, and geography rules are collected for every
    delivery country.
    """
    req = (
        db.query(Request)
        .options(
            joinedload(Request.delivery_countries),
            joinedload(Request.scenario_tags),
            joinedload(Request.category),
        )
        .filter(Request.request_id == request_id)
        .first()
    )
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")

    cat = req.category
    delivery_codes = [dc.country_code for dc in req.delivery_countries]
    countries_to_check = delivery_codes if delivery_codes else [req.country]
    regions = list(dict.fromkeys(
        COUNTRY_TO_REGION.get(c, "EU") for c in countries_to_check
    ))

    request_dict = {
        "request_id": req.request_id,
        "created_at": req.created_at.isoformat() if req.created_at else None,
        "request_channel": req.request_channel,
        "request_language": req.request_language,
        "business_unit": req.business_unit,
        "country": req.country,
        "site": req.site,
        "requester_id": req.requester_id,
        "requester_role": req.requester_role,
        "submitted_for_id": req.submitted_for_id,
        "category_id": req.category_id,
        "category_l1": cat.category_l1 if cat else None,
        "category_l2": cat.category_l2 if cat else None,
        "title": req.title,
        "request_text": req.request_text,
        "currency": req.currency,
        "budget_amount": str(req.budget_amount) if req.budget_amount is not None else None,
        "quantity": str(req.quantity) if req.quantity is not None else None,
        "unit_of_measure": req.unit_of_measure,
        "required_by_date": str(req.required_by_date),
        "preferred_supplier_mentioned": req.preferred_supplier_mentioned,
        "incumbent_supplier": req.incumbent_supplier,
        "contract_type_requested": req.contract_type_requested,
        "delivery_countries": delivery_codes,
        "data_residency_constraint": req.data_residency_constraint,
        "esg_requirement": req.esg_requirement,
        "status": req.status,
        "scenario_tags": [t.tag for t in req.scenario_tags],
    }

    # Compliant suppliers — must serve ALL delivery countries and not be
    # restricted in ANY of them.
    compliant = []
    if cat:
        restricted_ids: set[str] = set()
        for country in countries_to_check:
            sub = (
                db.query(RestrictedSupplierPolicy.supplier_id)
                .join(RestrictedSupplierScope)
                .filter(
                    RestrictedSupplierPolicy.category_l1 == cat.category_l1,
                    RestrictedSupplierPolicy.category_l2 == cat.category_l2,
                    or_(
                        RestrictedSupplierScope.scope_value == "all",
                        RestrictedSupplierScope.scope_value == country,
                    ),
                )
            )
            restricted_ids.update(row[0] for row in sub.all())

        candidate_sets: list[set[str]] = []
        for country in countries_to_check:
            ids = {
                row[0]
                for row in (
                    db.query(Supplier.supplier_id)
                    .join(SupplierCategory, Supplier.supplier_id == SupplierCategory.supplier_id)
                    .join(Category, SupplierCategory.category_id == Category.id)
                    .join(SupplierServiceRegion, Supplier.supplier_id == SupplierServiceRegion.supplier_id)
                    .filter(
                        Category.category_l1 == cat.category_l1,
                        Category.category_l2 == cat.category_l2,
                        SupplierServiceRegion.country_code == country,
                    )
                    .all()
                )
            }
            candidate_sets.append(ids)

        valid_ids = candidate_sets[0] if candidate_sets else set()
        for s in candidate_sets[1:]:
            valid_ids &= s
        valid_ids -= restricted_ids

        if valid_ids:
            supplier_rows = (
                db.query(
                    Supplier.supplier_id,
                    Supplier.supplier_name,
                    Supplier.country_hq,
                    Supplier.currency,
                    Supplier.capacity_per_month,
                    SupplierCategory.quality_score,
                    SupplierCategory.risk_score,
                    SupplierCategory.esg_score,
                    SupplierCategory.preferred_supplier,
                    SupplierCategory.data_residency_supported,
                )
                .join(SupplierCategory, Supplier.supplier_id == SupplierCategory.supplier_id)
                .join(Category, SupplierCategory.category_id == Category.id)
                .filter(
                    Category.category_l1 == cat.category_l1,
                    Category.category_l2 == cat.category_l2,
                    Supplier.supplier_id.in_(valid_ids),
                )
                .all()
            )

            compliant = [
                CompliantSupplierOut(
                    supplier_id=r.supplier_id,
                    supplier_name=r.supplier_name,
                    country_hq=r.country_hq,
                    currency=r.currency,
                    quality_score=r.quality_score,
                    risk_score=r.risk_score,
                    esg_score=r.esg_score,
                    preferred_supplier=r.preferred_supplier,
                    data_residency_supported=r.data_residency_supported,
                    capacity_per_month=r.capacity_per_month,
                )
                for r in supplier_rows
            ]

    # Pricing for compliant suppliers — look up across ALL unique regions.
    pricing = []
    quantity = int(req.quantity) if req.quantity is not None else None
    if cat and quantity is not None and compliant:
        for sup in compliant:
            for rgn in regions:
                pts = (
                    db.query(PricingTier)
                    .join(Category, PricingTier.category_id == Category.id)
                    .filter(
                        PricingTier.supplier_id == sup.supplier_id,
                        Category.category_l1 == cat.category_l1,
                        Category.category_l2 == cat.category_l2,
                        PricingTier.region == rgn,
                        PricingTier.min_quantity <= quantity,
                        PricingTier.max_quantity >= quantity,
                    )
                    .all()
                )
                for pt in pts:
                    pricing.append(
                        PricingLookupOut(
                            pricing_id=pt.pricing_id,
                            supplier_id=pt.supplier_id,
                            supplier_name=sup.supplier_name,
                            region=pt.region,
                            currency=pt.currency,
                            min_quantity=pt.min_quantity,
                            max_quantity=pt.max_quantity,
                            unit_price=pt.unit_price,
                            expedited_unit_price=pt.expedited_unit_price,
                            total_price=pt.unit_price * quantity,
                            expedited_total_price=pt.expedited_unit_price * quantity,
                            standard_lead_time_days=pt.standard_lead_time_days,
                            expedited_lead_time_days=pt.expedited_lead_time_days,
                            moq=pt.moq,
                        )
                    )

    # Applicable rules — collect for ALL delivery countries.
    rules = ApplicableRulesOut(category_rules=[], geography_rules=[])
    if cat:
        cat_rules = (
            db.query(CategoryRule)
            .join(Category, CategoryRule.category_id == Category.id)
            .filter(
                Category.category_l1 == cat.category_l1,
                Category.category_l2 == cat.category_l2,
            )
            .all()
        )

        seen_geo_ids: set[str] = set()
        all_geo: list[GeographyRule] = []
        for country in countries_to_check:
            single_geo = (
                db.query(GeographyRule)
                .filter(GeographyRule.country == country)
                .all()
            )
            region_geo = (
                db.query(GeographyRule)
                .join(GeographyRuleCountry)
                .join(GeographyRuleAppliesToCategory)
                .filter(
                    GeographyRuleCountry.country_code == country,
                    GeographyRuleAppliesToCategory.category_l1 == cat.category_l1,
                )
                .all()
            )
            for r in single_geo + region_geo:
                if r.rule_id not in seen_geo_ids:
                    seen_geo_ids.add(r.rule_id)
                    all_geo.append(r)

        rules = ApplicableRulesOut(
            category_rules=[
                {
                    "rule_id": r.rule_id,
                    "category_id": r.category_id,
                    "rule_type": r.rule_type,
                    "rule_text": r.rule_text,
                }
                for r in cat_rules
            ],
            geography_rules=[
                {
                    "rule_id": r.rule_id,
                    "country": r.country,
                    "region": r.region,
                    "rule_type": r.rule_type,
                    "rule_text": r.rule_text,
                }
                for r in all_geo
            ],
        )

    # Approval tier
    approval = None
    if req.budget_amount is not None:
        t = (
            db.query(ApprovalThreshold)
            .options(
                joinedload(ApprovalThreshold.managers),
                joinedload(ApprovalThreshold.deviation_approvers),
            )
            .filter(
                ApprovalThreshold.currency == req.currency,
                ApprovalThreshold.min_amount <= req.budget_amount,
                or_(
                    ApprovalThreshold.max_amount.is_(None),
                    ApprovalThreshold.max_amount >= req.budget_amount,
                ),
            )
            .first()
        )
        if t:
            approval = ApprovalTierOut(
                threshold_id=t.threshold_id,
                currency=t.currency,
                min_amount=t.min_amount,
                max_amount=t.max_amount,
                min_supplier_quotes=t.min_supplier_quotes,
                policy_note=t.policy_note,
                managers=[m.manager_role for m in t.managers],
                deviation_approvers=[d.approver_role for d in t.deviation_approvers],
            )

    # Historical awards
    awards = (
        db.query(HistoricalAward)
        .filter(HistoricalAward.request_id == request_id)
        .order_by(HistoricalAward.award_rank)
        .all()
    )
    awards_list = [
        {
            "award_id": a.award_id,
            "supplier_id": a.supplier_id,
            "supplier_name": a.supplier_name,
            "total_value": str(a.total_value),
            "currency": a.currency,
            "awarded": a.awarded,
            "award_rank": a.award_rank,
            "decision_rationale": a.decision_rationale,
            "savings_pct": str(a.savings_pct),
            "lead_time_days": a.lead_time_days,
        }
        for a in awards
    ]

    return RequestOverviewOut(
        request=request_dict,
        compliant_suppliers=compliant,
        pricing=pricing,
        applicable_rules=rules,
        approval_tier=approval,
        historical_awards=awards_list,
    )


# --- Aggregation Endpoints ---


@router.get("/spend-by-category", response_model=list[SpendByCategoryOut])
def spend_by_category(db: Session = Depends(get_db)):
    """Aggregated historical spend grouped by category (winners only)."""
    rows = (
        db.query(
            Category.category_l1,
            Category.category_l2,
            func.sum(HistoricalAward.total_value).label("total_spend"),
            func.count(HistoricalAward.award_id).label("award_count"),
            func.avg(HistoricalAward.savings_pct).label("avg_savings_pct"),
        )
        .join(Category, HistoricalAward.category_id == Category.id)
        .filter(HistoricalAward.awarded == True)
        .group_by(Category.category_l1, Category.category_l2)
        .order_by(func.sum(HistoricalAward.total_value).desc())
        .all()
    )

    return [
        SpendByCategoryOut(
            category_l1=r.category_l1,
            category_l2=r.category_l2,
            total_spend=r.total_spend,
            award_count=r.award_count,
            avg_savings_pct=round(r.avg_savings_pct, 2),
        )
        for r in rows
    ]


@router.get("/spend-by-supplier", response_model=list[SpendBySupplierOut])
def spend_by_supplier(db: Session = Depends(get_db)):
    """Aggregated historical spend grouped by supplier (winners only)."""
    rows = (
        db.query(
            HistoricalAward.supplier_id,
            HistoricalAward.supplier_name,
            func.sum(HistoricalAward.total_value).label("total_spend"),
            func.count(HistoricalAward.award_id).label("award_count"),
            func.avg(HistoricalAward.savings_pct).label("avg_savings_pct"),
        )
        .filter(HistoricalAward.awarded == True)
        .group_by(HistoricalAward.supplier_id, HistoricalAward.supplier_name)
        .order_by(func.sum(HistoricalAward.total_value).desc())
        .all()
    )

    return [
        SpendBySupplierOut(
            supplier_id=r.supplier_id,
            supplier_name=r.supplier_name,
            total_spend=r.total_spend,
            award_count=r.award_count,
            avg_savings_pct=round(r.avg_savings_pct, 2),
        )
        for r in rows
    ]


@router.get("/supplier-win-rates", response_model=list[SupplierWinRateOut])
def supplier_win_rates(db: Session = Depends(get_db)):
    """Win rates from historical awards per supplier."""
    rows = (
        db.query(
            HistoricalAward.supplier_id,
            HistoricalAward.supplier_name,
            func.count(HistoricalAward.award_id).label("total_evaluations"),
            func.sum(case((HistoricalAward.awarded == True, 1), else_=0)).label("wins"),
        )
        .group_by(HistoricalAward.supplier_id, HistoricalAward.supplier_name)
        .order_by(
            func.sum(case((HistoricalAward.awarded == True, 1), else_=0)).desc()
        )
        .all()
    )

    return [
        SupplierWinRateOut(
            supplier_id=r.supplier_id,
            supplier_name=r.supplier_name,
            total_evaluations=r.total_evaluations,
            wins=r.wins,
            win_rate=round(Decimal(r.wins) / Decimal(r.total_evaluations) * 100, 2)
            if r.total_evaluations > 0
            else Decimal(0),
        )
        for r in rows
    ]
