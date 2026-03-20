"""Step 9: Assemble final output with LLM enrichment."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.models.output import (
    ApprovalThresholdOutput,
    AuditTrailOutput,
    EscalationOutput,
    ExcludedSupplierOutput,
    PipelineOutput,
    PolicyEvaluationOutput,
    PreferredSupplierOutput,
    RecommendationOutput,
    RequestInterpretationOutput,
    RestrictionEvalOutput,
    ValidationIssueOutput,
    ValidationOutput,
)
from app.models.pipeline_io import (
    ComplianceResult,
    EscalationResult,
    FetchResult,
    LLMEnrichmentResult,
    PolicyResult,
    RankResult,
    RecommendationResult,
    ValidationResult,
)
from app.pipeline.logger import PipelineLogger

if TYPE_CHECKING:
    from app.clients.llm import LLMClient

logger = logging.getLogger(__name__)

STEP_NAME = "assemble_output"

ENRICHMENT_SYSTEM_PROMPT = """You are a procurement audit analyst. Enrich pipeline output concisely.

STRICT LENGTH RULES — violations will be rejected:
- Validation issue description: 1-2 sentences MAX. Include key numbers only.
- Validation issue action_required: 1 sentence MAX. State the single most important action.
- Supplier recommendation_note: 2-3 sentences MAX. State rank justification, one key strength, one key concern.

CONTENT RULES:
- Use specific figures (prices, scores, lead times) — no vague language.
- Do NOT repeat the supplier name or rank in the note (already shown in structured data).
- Do NOT list every metric — pick the 2-3 most decision-relevant ones.
- Professional, audit-ready language. No filler or preambles.
"""


async def assemble_output(
    fetch_result: FetchResult,
    validation_result: ValidationResult,
    compliance_result: ComplianceResult,
    rank_result: RankResult,
    policy_result: PolicyResult,
    escalation_result: EscalationResult,
    recommendation_result: RecommendationResult,
    run_id: str,
    llm_client: "LLMClient | None",
    pipeline_logger: PipelineLogger,
) -> PipelineOutput:
    """Combine all step outputs into the final response."""

    req = fetch_result.request
    interp = validation_result.request_interpretation
    currency = (req.currency or "EUR").lower()

    async with pipeline_logger.step(
        STEP_NAME,
        {"request_id": req.request_id},
    ) as ctx:

        # ── LLM enrichment ────────────────────────────────────

        enriched_issues = validation_result.issues
        supplier_notes: dict[str, str] = {}
        llm_enriched = False

        if llm_client and (validation_result.issues or rank_result.ranked_suppliers):
            llm_result, fallback = await _enrich_with_llm(
                llm_client, validation_result, rank_result, currency, pipeline_logger,
            )
            if llm_result and not fallback:
                llm_enriched = True
                issue_map = {e.issue_id: e for e in llm_result.enriched_issues}
                for issue in enriched_issues:
                    if issue.issue_id in issue_map:
                        enrichment = issue_map[issue.issue_id]
                        if enrichment.severity:
                            issue.severity = enrichment.severity
                        if enrichment.description:
                            issue.description = enrichment.description
                        if enrichment.action_required:
                            issue.action_required = enrichment.action_required

                for note in llm_result.supplier_notes:
                    supplier_notes[note.supplier_id] = note.recommendation_note

        # ── Request interpretation ────────────────────────────

        request_interpretation = RequestInterpretationOutput(
            category_l1=interp.category_l1,
            category_l2=interp.category_l2,
            quantity=interp.quantity,
            unit_of_measure=interp.unit_of_measure or req.unit_of_measure,
            budget_amount=interp.budget_amount,
            currency=interp.currency,
            delivery_country=interp.delivery_country,
            required_by_date=interp.required_by_date,
            days_until_required=interp.days_until_required,
            data_residency_required=interp.data_residency_required,
            esg_requirement=interp.esg_requirement,
            preferred_supplier_stated=interp.preferred_supplier_stated,
            incumbent_supplier=interp.incumbent_supplier,
            requester_instruction=interp.requester_instruction,
        )

        # ── Validation ────────────────────────────────────────

        completeness_str = "pass" if validation_result.completeness else "fail"
        validation_output = ValidationOutput(
            completeness=completeness_str,
            issues_detected=[
                ValidationIssueOutput(
                    issue_id=i.issue_id,
                    severity=i.severity,
                    type=i.type,
                    description=i.description,
                    action_required=i.action_required,
                )
                for i in enriched_issues
            ],
            llm_used=validation_result.llm_used,
            llm_fallback=validation_result.llm_fallback,
        )

        # ── Policy evaluation ─────────────────────────────────

        pe = policy_result
        policy_output = PolicyEvaluationOutput(
            approval_threshold=ApprovalThresholdOutput(
                rule_applied=pe.approval_threshold.rule_applied,
                basis=pe.approval_threshold.basis,
                quotes_required=pe.approval_threshold.quotes_required,
                approvers=pe.approval_threshold.approvers,
                deviation_approval=pe.approval_threshold.deviation_approval,
                note=pe.approval_threshold.note,
            ),
            preferred_supplier=PreferredSupplierOutput(
                supplier=pe.preferred_supplier.supplier,
                status=pe.preferred_supplier.status,
                is_preferred=pe.preferred_supplier.is_preferred,
                covers_delivery_country=pe.preferred_supplier.covers_delivery_country,
                is_restricted=pe.preferred_supplier.is_restricted,
                policy_note=pe.preferred_supplier.policy_note,
            ),
            restricted_suppliers={
                k: RestrictionEvalOutput(restricted=v.restricted, note=v.note)
                for k, v in pe.restricted_suppliers.items()
            },
            category_rules_applied=[
                r.model_dump() for r in pe.category_rules_applied
            ],
            geography_rules_applied=[
                r.model_dump() for r in pe.geography_rules_applied
            ],
        )

        # ── Supplier shortlist (dynamic currency keys) ────────

        supplier_shortlist: list[dict] = []
        for s in rank_result.ranked_suppliers:
            note = supplier_notes.get(s.supplier_id, s.recommendation_note)
            entry: dict = {
                "rank": s.rank,
                "supplier_id": s.supplier_id,
                "supplier_name": s.supplier_name,
                "preferred": s.preferred,
                "incumbent": s.incumbent,
                "pricing_tier_applied": s.pricing_tier_applied,
                f"unit_price_{currency}": s.unit_price,
                f"total_price_{currency}": s.total_price,
                "standard_lead_time_days": s.standard_lead_time_days,
                "expedited_lead_time_days": s.expedited_lead_time_days,
                f"expedited_unit_price_{currency}": s.expedited_unit_price,
                f"expedited_total_{currency}": s.expedited_total_price,
                "quality_score": s.quality_score,
                "risk_score": s.risk_score,
                "esg_score": s.esg_score,
                "policy_compliant": s.policy_compliant,
                "covers_delivery_country": s.covers_delivery_country,
                "recommendation_note": note,
            }
            supplier_shortlist.append(entry)

        # ── Suppliers excluded ────────────────────────────────

        suppliers_excluded = [
            ExcludedSupplierOutput(
                supplier_id=e.supplier_id,
                supplier_name=e.supplier_name,
                reason=e.reason,
            )
            for e in compliance_result.excluded
        ]

        # ── Escalations ──────────────────────────────────────

        escalations = [
            EscalationOutput(
                escalation_id=e.escalation_id,
                rule=e.rule,
                trigger=e.trigger,
                escalate_to=e.escalate_to,
                blocking=e.blocking,
            )
            for e in escalation_result.escalations
        ]

        # ── Recommendation ────────────────────────────────────

        recommendation = RecommendationOutput(
            status=recommendation_result.status,
            reason=recommendation_result.reason,
            preferred_supplier_if_resolved=recommendation_result.preferred_supplier_if_resolved,
            preferred_supplier_rationale=recommendation_result.preferred_supplier_rationale,
            minimum_budget_required=recommendation_result.minimum_budget_required,
            minimum_budget_currency=recommendation_result.minimum_budget_currency,
            confidence_score=recommendation_result.confidence_score,
            llm_used=recommendation_result.llm_used,
            llm_fallback=recommendation_result.llm_fallback,
        )

        # ── Audit trail ───────────────────────────────────────

        audit_trail = _build_audit_trail(
            fetch_result, policy_result, rank_result, compliance_result, pipeline_logger,
        )

        # ── Final output ──────────────────────────────────────

        is_valid = validation_result.completeness
        output = PipelineOutput(
            request_id=req.request_id,
            processed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            run_id=run_id,
            status="processed" if is_valid else "invalid",
            request_interpretation=request_interpretation,
            validation=validation_output,
            policy_evaluation=policy_output,
            supplier_shortlist=supplier_shortlist,
            suppliers_excluded=suppliers_excluded,
            escalations=escalations,
            recommendation=recommendation,
            audit_trail=audit_trail,
        )

        ctx.output_summary = {
            "sections": 8,
            "llm_enriched": llm_enriched,
        }
        ctx.metadata = {
            "sections": 8,
            "llm_enriched": llm_enriched,
        }

        return output


async def _enrich_with_llm(
    llm_client: "LLMClient",
    validation_result: ValidationResult,
    rank_result: RankResult,
    currency: str,
    pipeline_logger: PipelineLogger,
) -> tuple["LLMEnrichmentResult | None", bool]:
    """Call LLM to enrich validation issues and generate supplier notes."""

    parts = ["Enrich the following pipeline output:\n"]

    if validation_result.issues:
        parts.append("## Validation Issues")
        for i in validation_result.issues:
            parts.append(
                f"- {i.issue_id} [{i.severity}] {i.type}: {i.description}"
            )

    if rank_result.ranked_suppliers:
        parts.append("\n## Ranked Suppliers")
        for s in rank_result.ranked_suppliers:
            price = (
                f"{currency.upper()} {s.total_price:,.2f}"
                if s.total_price
                else "N/A"
            )
            parts.append(
                f"- #{s.rank} {s.supplier_id} ({s.supplier_name}): {price}, "
                f"quality={s.quality_score}, risk={s.risk_score}, esg={s.esg_score}, "
                f"lead_standard={s.standard_lead_time_days}d, "
                f"lead_expedited={s.expedited_lead_time_days}d, "
                f"preferred={s.preferred}, incumbent={s.incumbent}"
            )

    parts.append(
        "\nFor each issue: severity + 1-2 sentence description + 1 sentence action. "
        "For each supplier: 2-3 sentence recommendation note with key differentiators only."
    )

    result, fallback = await llm_client.structured_call(
        system_prompt=ENRICHMENT_SYSTEM_PROMPT,
        user_prompt="\n".join(parts),
        response_model=LLMEnrichmentResult,
        max_tokens=1500,
    )

    if fallback:
        pipeline_logger.audit(
            "general", "warn", STEP_NAME,
            "LLM call failed for enrichment. Using deterministic output.",
        )

    return result, fallback


def _build_audit_trail(
    fetch_result: FetchResult,
    policy_result: PolicyResult,
    rank_result: RankResult,
    compliance_result: ComplianceResult,
    pipeline_logger: PipelineLogger,
) -> AuditTrailOutput:
    """Build the audit trail section from pipeline data."""

    # Policies checked
    policies: set[str] = set()
    if policy_result.approval_threshold.rule_applied:
        policies.add(policy_result.approval_threshold.rule_applied)
    for r in policy_result.category_rules_applied:
        policies.add(r.rule_id)
    for r in policy_result.geography_rules_applied:
        policies.add(r.rule_id)
    # Add escalation rules from audit buffer
    for entry in pipeline_logger.collected_audit_entries:
        details = entry.get("details", {})
        if details.get("rule_id"):
            policies.add(details["rule_id"])
        if details.get("policy_id"):
            policies.add(details["policy_id"])

    # Supplier IDs evaluated
    supplier_ids: set[str] = set()
    for s in fetch_result.compliant_suppliers:
        supplier_ids.add(s.supplier_id)
    for e in compliance_result.excluded:
        supplier_ids.add(e.supplier_id)

    # Pricing tiers
    pricing_tiers_applied = ""
    if rank_result.ranked_suppliers:
        first = rank_result.ranked_suppliers[0]
        if first.pricing_tier_applied:
            currency = first.currency or "EUR"
            delivery_country = fetch_result.request.country or "DE"
            from app.utils import country_to_region
            region = country_to_region(delivery_country)
            pricing_tiers_applied = (
                f"{first.pricing_tier_applied} "
                f"({region} region, {currency} currency)"
            )

    # Data sources
    data_sources = ["requests.json", "suppliers.csv", "pricing.csv", "policies.json"]
    has_awards = len(fetch_result.historical_awards) > 0
    if has_awards:
        data_sources.append("historical_awards.csv")

    # Historical award note
    award_note = ""
    if has_awards:
        awards = fetch_result.historical_awards
        award_ids = [a.award_id for a in awards[:5]]
        awarded_to = [a.supplier_name for a in awards if a.awarded]
        ids_str = ", ".join(award_ids)
        if awarded_to:
            award_note = (
                f"{ids_str} show this request was previously evaluated. "
                f"Awarded to {awarded_to[0]}. Prior decision used for pattern context only."
            )
        else:
            award_note = f"{ids_str} show prior evaluations for this request."

    return AuditTrailOutput(
        policies_checked=sorted(policies),
        supplier_ids_evaluated=sorted(supplier_ids),
        pricing_tiers_applied=pricing_tiers_applied,
        data_sources_used=data_sources,
        historical_awards_consulted=has_awards,
        historical_award_note=award_note,
    )
