from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
import re

from sqlalchemy.orm import Session, joinedload

from app.models.policies import (
    ApprovalThreshold,
    EscalationRule,
    RestrictedSupplierPolicy,
)
from app.models.reference import PricingTier, Supplier
from app.models.requests import Request

COUNTRY_TO_REGION = {
    "DE": "EU",
    "FR": "EU",
    "NL": "EU",
    "BE": "EU",
    "AT": "EU",
    "IT": "EU",
    "ES": "EU",
    "PL": "EU",
    "UK": "EU",
    "CH": "CH",
    "US": "Americas",
    "CA": "Americas",
    "BR": "Americas",
    "MX": "Americas",
    "SG": "APAC",
    "AU": "APAC",
    "IN": "APAC",
    "JP": "APAC",
    "UAE": "MEA",
    "ZA": "MEA",
}

SINGLE_SUPPLIER_PATTERNS = [
    re.compile(
        r"\b(single\s+supplier|sole\s+source|one\s+supplier|only\s+supplier)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(no\s+exception|without\s+exceptions)\b", re.IGNORECASE),
    re.compile(r"fournisseur\s+unique|sans\s+exception", re.IGNORECASE),
    re.compile(r"proveedor\s+unico|sin\s+excepc", re.IGNORECASE),
    re.compile(r"fornecedor\s+unico|sem\s+exce", re.IGNORECASE),
    re.compile(r"einzige[nr]?\s+lieferant|ohne\s+ausnahme", re.IGNORECASE),
    re.compile(r"単一\s*サプライヤー|例外なし"),
]

CONDITIONAL_THRESHOLD_PATTERN = re.compile(
    r"\bbelow\s+(EUR|CHF|USD)\s*([0-9][0-9\s,\.]*)\b",
    re.IGNORECASE,
)


@dataclass
class CandidateSupplier:
    supplier_id: str
    supplier_name: str
    covers_delivery_scope: bool
    restricted: bool
    data_residency_supported: bool
    capacity_per_month: int
    total_price: Decimal | None


@dataclass
class EscalationRuleInput:
    request_id: str
    title: str
    created_at: datetime
    business_unit: str
    country_scope: str
    category_label: str
    request_status: str
    request_text: str
    request_currency: str
    missing_required_information: bool
    preferred_supplier_restricted: bool
    has_compliant_priceable_supplier: bool
    has_residency_compatible_supplier: bool | None
    single_supplier_capacity_risk: bool
    preferred_supplier_unregistered_usd: bool
    threshold_id: str | None
    threshold_quotes_required: int
    threshold_managers: list[str]
    threshold_deviation_approvers: list[str]


@dataclass
class ComputedEscalation:
    rule_id: str
    rule_label: str
    trigger: str
    escalate_to: str
    blocking: bool


def has_single_supplier_instruction(request_text: str) -> bool:
    text = request_text or ""
    return any(pattern.search(text) for pattern in SINGLE_SUPPLIER_PATTERNS)


def parse_conditional_threshold(
    restriction_reason: str,
) -> tuple[str, Decimal] | None:
    match = CONDITIONAL_THRESHOLD_PATTERN.search(restriction_reason or "")
    if not match:
        return None

    raw_amount = re.sub(r"[^0-9.]", "", match.group(2))
    if not raw_amount:
        return None

    try:
        amount = Decimal(raw_amount)
    except Exception:
        return None
    return match.group(1).upper(), amount


def is_restriction_active(
    restriction_reason: str,
    request_currency: str,
    evaluated_amount: Decimal | None,
) -> bool:
    conditional = parse_conditional_threshold(restriction_reason)
    if not conditional:
        return True

    conditional_currency, conditional_amount = conditional
    if conditional_currency != request_currency.upper():
        return True
    if evaluated_amount is None:
        return True
    return evaluated_amount >= conditional_amount


def compute_escalations_for_rule_input(
    rule_input: EscalationRuleInput,
    escalation_rule_labels: dict[str, str],
    escalation_rule_targets: dict[str, str],
) -> list[ComputedEscalation]:
    rows: list[ComputedEscalation] = []

    def add_er(rule_id: str, trigger: str, blocking: bool = True):
        if rule_id not in escalation_rule_targets:
            return
        rows.append(
            ComputedEscalation(
                rule_id=rule_id,
                rule_label=escalation_rule_labels.get(rule_id, rule_id),
                trigger=trigger,
                escalate_to=escalation_rule_targets[rule_id],
                blocking=blocking,
            )
        )

    if rule_input.missing_required_information:
        add_er(
            "ER-001",
            "Missing required request information (budget, quantity, or category context).",
            blocking=True,
        )

    if rule_input.preferred_supplier_restricted:
        add_er(
            "ER-002",
            "Preferred supplier is restricted for this request context.",
            blocking=True,
        )

    strategic_roles = {
        "head of strategic sourcing",
        "cpo",
    }
    strategic_actors = [
        *rule_input.threshold_managers,
        *rule_input.threshold_deviation_approvers,
    ]
    if any(role.strip().lower() in strategic_roles for role in strategic_actors):
        add_er(
            "ER-003",
            "Evaluated contract value falls into strategic sourcing approval tier.",
            blocking=False,
        )

    if (
        not rule_input.missing_required_information
        and not rule_input.has_compliant_priceable_supplier
    ):
        add_er(
            "ER-004",
            "No compliant supplier with valid pricing can be identified.",
            blocking=True,
        )

    if (
        not rule_input.missing_required_information
        and
        rule_input.has_residency_compatible_supplier is not None
        and not rule_input.has_residency_compatible_supplier
    ):
        add_er(
            "ER-005",
            "Data residency requirement cannot be satisfied by available compliant suppliers.",
            blocking=True,
        )

    if (
        not rule_input.missing_required_information
        and rule_input.single_supplier_capacity_risk
    ):
        add_er(
            "ER-006",
            "Only one supplier can satisfy the required quantity/capacity constraints.",
            blocking=True,
        )

    if rule_input.category_label == "Marketing / Influencer Campaign Management":
        add_er(
            "ER-007",
            "Brand-safety review is required before final award in influencer campaigns.",
            blocking=True,
        )

    if rule_input.preferred_supplier_unregistered_usd:
        add_er(
            "ER-008",
            "Preferred supplier is not registered for all delivery countries in this USD request.",
            blocking=True,
        )

    if (
        rule_input.threshold_id
        and rule_input.threshold_quotes_required >= 2
        and has_single_supplier_instruction(rule_input.request_text)
    ):
        if rule_input.threshold_deviation_approvers:
            escalation_target = rule_input.threshold_deviation_approvers[0]
        elif rule_input.threshold_managers:
            escalation_target = rule_input.threshold_managers[0]
        else:
            escalation_target = "Procurement Manager"

        rows.append(
            ComputedEscalation(
                rule_id=rule_input.threshold_id,
                rule_label="policy_threshold_conflict",
                trigger=(
                    f"Requester instruction conflicts with {rule_input.threshold_id}: "
                    f"{rule_input.threshold_quotes_required} quotes are required."
                ),
                escalate_to=escalation_target,
                blocking=True,
            )
        )

    return rows


def evaluate_escalation_queue(
    db: Session,
    request_id: str | None = None,
) -> list[dict]:
    requests_query = db.query(Request).options(
        joinedload(Request.category),
        joinedload(Request.delivery_countries),
    )
    if request_id:
        requests_query = requests_query.filter(Request.request_id == request_id)

    requests = requests_query.order_by(Request.request_id).all()

    escalation_rules = db.query(EscalationRule).options(
        joinedload(EscalationRule.currencies)
    ).all()
    escalation_rule_labels = {
        rule.rule_id: rule.trigger_condition for rule in escalation_rules
    }
    escalation_rule_targets = {
        rule.rule_id: rule.escalate_to for rule in escalation_rules
    }

    thresholds = db.query(ApprovalThreshold).options(
        joinedload(ApprovalThreshold.managers),
        joinedload(ApprovalThreshold.deviation_approvers),
    ).all()
    thresholds_by_currency: dict[str, list[ApprovalThreshold]] = {}
    for threshold in thresholds:
        thresholds_by_currency.setdefault(threshold.currency, []).append(threshold)
    for values in thresholds_by_currency.values():
        values.sort(key=lambda t: t.min_amount)

    suppliers = db.query(Supplier).options(
        joinedload(Supplier.categories),
        joinedload(Supplier.service_regions),
    ).all()
    suppliers_by_name = {supplier.supplier_name.lower(): supplier for supplier in suppliers}

    restricted_policies = db.query(RestrictedSupplierPolicy).options(
        joinedload(RestrictedSupplierPolicy.scopes)
    ).all()
    restricted_by_supplier_category: dict[tuple[str, str, str], list[RestrictedSupplierPolicy]] = {}
    for policy in restricted_policies:
        key = (policy.supplier_id, policy.category_l1, policy.category_l2)
        restricted_by_supplier_category.setdefault(key, []).append(policy)

    pricing_tiers = db.query(PricingTier).all()
    pricing_by_supplier_category_region: dict[tuple[str, int, str], list[PricingTier]] = {}
    for tier in pricing_tiers:
        key = (tier.supplier_id, tier.category_id, tier.region)
        pricing_by_supplier_category_region.setdefault(key, []).append(tier)
    for values in pricing_by_supplier_category_region.values():
        values.sort(key=lambda tier: tier.min_quantity)

    rows: list[dict] = []
    for request in requests:
        delivery_countries = [entry.country_code for entry in request.delivery_countries]
        if not delivery_countries:
            delivery_countries = [request.country]
        country_scope = ", ".join(delivery_countries)

        category_l1 = request.category.category_l1 if request.category else None
        category_l2 = request.category.category_l2 if request.category else None
        category_label = (
            f"{category_l1} / {category_l2}"
            if category_l1 and category_l2
            else "Unknown category"
        )

        quantity = int(request.quantity) if request.quantity is not None else None
        region = COUNTRY_TO_REGION.get(delivery_countries[0], "EU")

        candidates: list[CandidateSupplier] = []
        for supplier in suppliers:
            category_entry = next(
                (
                    entry
                    for entry in supplier.categories
                    if entry.category_id == request.category_id
                ),
                None,
            )
            if not category_entry:
                continue

            service_countries = {entry.country_code for entry in supplier.service_regions}
            covers_delivery_scope = set(delivery_countries).issubset(service_countries)

            restricted = False
            policy_key = (
                supplier.supplier_id,
                category_l1 or "",
                category_l2 or "",
            )
            policies = restricted_by_supplier_category.get(policy_key, [])
            for policy in policies:
                scopes = {scope.scope_value for scope in policy.scopes}
                scope_matches = "all" in scopes or any(
                    country in scopes for country in delivery_countries
                )
                if not scope_matches:
                    continue

                evaluated_amount = request.budget_amount
                if is_restriction_active(
                    policy.restriction_reason,
                    request.currency,
                    evaluated_amount,
                ):
                    restricted = True
                    break

            total_price: Decimal | None = None
            if quantity is not None:
                tier_key = (supplier.supplier_id, request.category_id, region)
                tiers = pricing_by_supplier_category_region.get(tier_key, [])
                for tier in tiers:
                    if (
                        tier.currency == request.currency
                        and tier.min_quantity <= quantity <= tier.max_quantity
                    ):
                        total_price = tier.unit_price * quantity
                        break

            candidates.append(
                CandidateSupplier(
                    supplier_id=supplier.supplier_id,
                    supplier_name=supplier.supplier_name,
                    covers_delivery_scope=covers_delivery_scope,
                    restricted=restricted,
                    data_residency_supported=category_entry.data_residency_supported,
                    capacity_per_month=supplier.capacity_per_month,
                    total_price=total_price,
                )
            )

        preferred_supplier = None
        if request.preferred_supplier_mentioned:
            preferred_supplier = suppliers_by_name.get(
                request.preferred_supplier_mentioned.lower()
            )
            if not preferred_supplier:
                preferred_supplier = next(
                    (
                        supplier
                        for supplier in suppliers
                        if request.preferred_supplier_mentioned.lower()
                        in supplier.supplier_name.lower()
                    ),
                    None,
                )

        preferred_supplier_restricted = False
        preferred_supplier_unregistered_usd = False
        if preferred_supplier and category_l1 and category_l2:
            service_countries = {
                region.country_code for region in preferred_supplier.service_regions
            }
            preferred_covers_scope = set(delivery_countries).issubset(service_countries)
            if request.currency == "USD" and not preferred_covers_scope:
                preferred_supplier_unregistered_usd = True

            policy_key = (
                preferred_supplier.supplier_id,
                category_l1,
                category_l2,
            )
            policies = restricted_by_supplier_category.get(policy_key, [])
            for policy in policies:
                scopes = {scope.scope_value for scope in policy.scopes}
                scope_matches = "all" in scopes or any(
                    country in scopes for country in delivery_countries
                )
                if not scope_matches:
                    continue
                if is_restriction_active(
                    policy.restriction_reason,
                    request.currency,
                    request.budget_amount,
                ):
                    preferred_supplier_restricted = True
                    break

        priceable_candidates = [
            candidate
            for candidate in candidates
            if candidate.covers_delivery_scope
            and not candidate.restricted
            and candidate.total_price is not None
        ]
        has_compliant_priceable_supplier = len(priceable_candidates) > 0

        if request.data_residency_constraint:
            residency_candidates = [
                candidate
                for candidate in priceable_candidates
                if candidate.data_residency_supported
            ]
            has_residency_compatible_supplier: bool | None = (
                len(residency_candidates) > 0
            )
        else:
            residency_candidates = priceable_candidates
            has_residency_compatible_supplier = None

        capacity_candidates = []
        if quantity is not None:
            capacity_candidates = [
                candidate
                for candidate in residency_candidates
                if candidate.capacity_per_month >= quantity
            ]
        single_supplier_capacity_risk = (
            quantity is not None and len(capacity_candidates) == 1
        )

        estimated_total_value: Decimal | None = None
        if priceable_candidates:
            estimated_total_value = min(
                candidate.total_price
                for candidate in priceable_candidates
                if candidate.total_price is not None
            )
        elif request.budget_amount is not None:
            estimated_total_value = request.budget_amount

        threshold_id = None
        threshold_quotes_required = 0
        threshold_managers: list[str] = []
        threshold_deviation_approvers: list[str] = []
        if estimated_total_value is not None:
            for threshold in thresholds_by_currency.get(request.currency, []):
                in_range = (
                    threshold.min_amount <= estimated_total_value
                    and (
                        threshold.max_amount is None
                        or threshold.max_amount >= estimated_total_value
                    )
                )
                if not in_range:
                    continue
                threshold_id = threshold.threshold_id
                threshold_quotes_required = threshold.min_supplier_quotes
                threshold_managers = [
                    manager.manager_role for manager in threshold.managers
                ]
                threshold_deviation_approvers = [
                    approver.approver_role
                    for approver in threshold.deviation_approvers
                ]
                break

        rule_input = EscalationRuleInput(
            request_id=request.request_id,
            title=request.title,
            created_at=request.created_at,
            business_unit=request.business_unit,
            country_scope=country_scope,
            category_label=category_label,
            request_status=request.status,
            request_text=request.request_text,
            request_currency=request.currency,
            missing_required_information=(
                request.budget_amount is None
                or request.quantity is None
                or request.category is None
                or category_l1 is None
                or category_l2 is None
            ),
            preferred_supplier_restricted=preferred_supplier_restricted,
            has_compliant_priceable_supplier=has_compliant_priceable_supplier,
            has_residency_compatible_supplier=has_residency_compatible_supplier,
            single_supplier_capacity_risk=single_supplier_capacity_risk,
            preferred_supplier_unregistered_usd=preferred_supplier_unregistered_usd,
            threshold_id=threshold_id,
            threshold_quotes_required=threshold_quotes_required,
            threshold_managers=threshold_managers,
            threshold_deviation_approvers=threshold_deviation_approvers,
        )

        computed = compute_escalations_for_rule_input(
            rule_input=rule_input,
            escalation_rule_labels=escalation_rule_labels,
            escalation_rule_targets=escalation_rule_targets,
        )
        if not computed:
            continue

        status = "resolved" if request.status == "resolved" else "open"
        recommendation_status = (
            "proceed"
            if status == "resolved"
            else "cannot_proceed"
            if any(item.blocking for item in computed)
            else "proceed_with_conditions"
        )

        for item in computed:
            rows.append(
                {
                    "escalation_id": f"{request.request_id}-{item.rule_id}",
                    "request_id": request.request_id,
                    "title": request.title,
                    "category": category_label,
                    "business_unit": request.business_unit,
                    "country": country_scope,
                    "rule_id": item.rule_id,
                    "rule_label": item.rule_label,
                    "trigger": item.trigger,
                    "escalate_to": item.escalate_to,
                    "blocking": item.blocking,
                    "status": status,
                    "created_at": request.created_at,
                    "last_updated": request.created_at,
                    "recommendation_status": recommendation_status,
                }
            )

    rows.sort(
        key=lambda row: (
            row["created_at"],
            row["request_id"],
            row["rule_id"],
        ),
        reverse=True,
    )
    return rows
