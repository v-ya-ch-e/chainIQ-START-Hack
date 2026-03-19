"""PipelineRunner: orchestrates the full 9-step procurement pipeline."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from app.clients.llm import LLMClient
from app.clients.organisational import OrganisationalClient
from app.models.output import (
    PipelineOutput,
    RecommendationOutput,
    RequestInterpretationOutput,
    ValidationOutput,
    ValidationIssueOutput,
    EscalationOutput,
    AuditTrailOutput,
    PolicyEvaluationOutput,
)
from app.pipeline.logger import PipelineLogger
from app.pipeline.rule_engine import RuleEngine
from app.pipeline.steps.assemble import assemble_output
from app.pipeline.steps.comply import check_compliance
from app.pipeline.steps.escalate import compute_escalations
from app.pipeline.steps.fetch import fetch_overview
from app.pipeline.steps.filter import filter_suppliers
from app.pipeline.steps.policy import evaluate_policy
from app.pipeline.steps.rank import rank_suppliers
from app.pipeline.steps.recommend import generate_recommendation
from app.pipeline.steps.validate import validate_request

logger = logging.getLogger(__name__)


class PipelineRunner:
    """Orchestrates the full 9-step procurement decision pipeline."""

    def __init__(
        self,
        org_client: OrganisationalClient,
        llm_client: LLMClient | None,
    ):
        self.org = org_client
        self.llm = llm_client
        self._results: dict[str, PipelineOutput] = {}

    async def process(self, request_id: str) -> PipelineOutput:
        """Run the full pipeline for a single request."""

        run_id = str(uuid.uuid4())
        pl = PipelineLogger(self.org, run_id, request_id)
        rule_engine = RuleEngine(llm_client=self.llm)

        try:
            # Set request to in_review
            await self.org.update_request_status(request_id, "in_review")
            await pl.start_run()

            # Fetch all active dynamic rules once
            all_rules = await self.org.get_active_rules()
            rules_by_stage: dict[str, list] = {}
            for r in all_rules:
                stage = r.get("pipeline_stage", "")
                rules_by_stage.setdefault(stage, []).append(r)

            # ── Step 1: Fetch ─────────────────────────────────
            fetch_result = await fetch_overview(request_id, self.org, pl)
            await pl.flush_audit()

            # ── Step 2: Validate ──────────────────────────────
            validation_result = await validate_request(
                fetch_result, self.llm, pl,
                rule_engine=rule_engine,
                dynamic_rules=rules_by_stage.get("validate", []),
            )
            await pl.flush_audit()

            # ── Branch: early exit on invalid ─────────────────
            if not validation_result.completeness:
                output = await self._format_invalid_response(
                    fetch_result, validation_result, run_id, pl,
                )
                await self.org.save_pipeline_result(
                    run_id=run_id,
                    request_id=request_id,
                    processed_at=output.processed_at,
                    output=output.model_dump(),
                    status=output.status,
                    recommendation_status=output.recommendation.status,
                )
                await self.org.update_request_status(request_id, "error")
                await pl.finalize_run("completed")
                await pl.flush_audit()
                self._results[request_id] = output
                return output

            # ── Step 3: Filter ────────────────────────────────
            filter_result = await filter_suppliers(fetch_result, pl)
            await pl.flush_audit()

            # ── Step 4: Comply ────────────────────────────────
            compliance_result = await check_compliance(
                fetch_result, filter_result, self.org, pl,
                rule_engine=rule_engine,
                dynamic_rules=rules_by_stage.get("comply", []),
            )
            await pl.flush_audit()

            # ── Step 5: Rank ──────────────────────────────────
            rank_result = await rank_suppliers(
                fetch_result, compliance_result, pl,
                validation_result=validation_result,
            )
            await pl.flush_audit()

            # ── Steps 6 & 7: Policy + Escalations (parallel) ─
            policy_task = evaluate_policy(
                fetch_result, rank_result, compliance_result, pl,
                rule_engine=rule_engine,
                dynamic_rules=rules_by_stage.get("policy", []),
            )
            escalation_task = compute_escalations(
                fetch_result, validation_result, compliance_result, rank_result, pl,
                rule_engine=rule_engine,
                dynamic_rules=rules_by_stage.get("escalate", []),
            )
            policy_result, escalation_result = await asyncio.gather(
                policy_task, escalation_task,
            )
            await pl.flush_audit()

            # ── Step 8: Recommend ─────────────────────────────
            recommendation_result = await generate_recommendation(
                fetch_result, validation_result, rank_result,
                escalation_result, self.llm, pl,
            )
            await pl.flush_audit()

            # ── Step 9: Assemble ──────────────────────────────
            output = await assemble_output(
                fetch_result=fetch_result,
                validation_result=validation_result,
                compliance_result=compliance_result,
                rank_result=rank_result,
                policy_result=policy_result,
                escalation_result=escalation_result,
                recommendation_result=recommendation_result,
                run_id=run_id,
                llm_client=self.llm,
                pipeline_logger=pl,
            )
            await pl.flush_audit()

            # ── Persist evaluation run (hard_rule_checks, policy_checks, supplier_evaluations) ─
            output_dict = output.model_dump()
            try:
                await self.org.persist_evaluation_run(
                    request_id=request_id,
                    run_id=run_id,
                    output_snapshot=output_dict,
                    triggered_by="agent",
                    agent_version="1.0",
                    trigger_reason="pipeline_complete",
                )
            except Exception as exc:
                logger.warning("Failed to persist evaluation run: %s", exc)

            # ── Persist full pipeline result for frontend ─────
            await self.org.save_pipeline_result(
                run_id=run_id,
                request_id=request_id,
                processed_at=output.processed_at,
                output=output_dict,
                status=output.status,
                recommendation_status=output.recommendation.status,
            )

            # ── Update request status ─────────────────────────
            if recommendation_result.status == "cannot_proceed":
                await self.org.update_request_status(request_id, "escalated")
            else:
                await self.org.update_request_status(request_id, "evaluated")

            await pl.finalize_run("completed")
            self._results[request_id] = output
            return output

        except Exception as exc:
            logger.exception("Pipeline failed for %s", request_id)
            await self.org.update_request_status(request_id, "error")
            await pl.finalize_run("failed", error_message=str(exc))
            raise

    async def _format_invalid_response(
        self,
        fetch_result,
        validation_result,
        run_id: str,
        pl: PipelineLogger,
    ) -> PipelineOutput:
        """Format an early-exit response for invalid requests."""

        async with pl.step("format_invalid_response", {"completeness": False}) as ctx:
            interp = validation_result.request_interpretation
            req = fetch_result.request

            output = PipelineOutput(
                request_id=req.request_id,
                processed_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                run_id=run_id,
                status="invalid",
                request_interpretation=RequestInterpretationOutput(
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
                ),
                validation=ValidationOutput(
                    completeness="fail",
                    issues_detected=[
                        ValidationIssueOutput(
                            issue_id=i.issue_id,
                            severity=i.severity,
                            type=i.type,
                            description=i.description,
                            action_required=i.action_required,
                        )
                        for i in validation_result.issues
                    ],
                    llm_used=validation_result.llm_used,
                    llm_fallback=validation_result.llm_fallback,
                ),
                policy_evaluation=PolicyEvaluationOutput(),
                supplier_shortlist=[],
                suppliers_excluded=[],
                escalations=[
                    EscalationOutput(
                        escalation_id="ESC-001",
                        rule="ER-001",
                        trigger="Request is missing critical required fields and cannot be processed.",
                        escalate_to="Requester Clarification",
                        blocking=True,
                    ),
                ],
                recommendation=RecommendationOutput(
                    status="cannot_proceed",
                    reason="Request is missing critical required fields (category and/or currency). Cannot proceed with supplier evaluation.",
                    confidence_score=0,
                    llm_used=False,
                    llm_fallback=False,
                ),
                audit_trail=AuditTrailOutput(
                    data_sources_used=["requests.json"],
                ),
            )

            ctx.output_summary = {"status": "invalid"}
            ctx.metadata = {"status": "invalid"}
            return output

    def get_cached_result(self, request_id: str) -> PipelineOutput | None:
        """Retrieve a cached pipeline result."""
        return self._results.get(request_id)
