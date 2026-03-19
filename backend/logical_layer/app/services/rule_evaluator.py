"""Async rule evaluator supporting expression, LLM, and hardcoded modes."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from simpleeval import SimpleEval

logger = logging.getLogger(__name__)

MAX_CONCURRENT_LLM = 5


def _safe_context(context: dict[str, Any]) -> dict[str, Any]:
    """Merge context with built-in names needed for expressions."""
    base = {"None": None, "True": True, "False": False}
    return {**base, **context}


def evaluate_expression(condition_expr: str, context: dict[str, Any]) -> bool:
    """Safely evaluate a Python expression against a context dict using simpleeval."""
    if not condition_expr or not condition_expr.strip():
        return False
    try:
        names = _safe_context(context)
        evaluator = SimpleEval(names=names)
        result = evaluator.eval(condition_expr.strip())
        return bool(result)
    except Exception as exc:
        logger.warning("Rule expression evaluation failed: %s — %s", condition_expr[:80], exc)
        return False


def _format_template(template: str, context: dict[str, Any]) -> str:
    """Replace {field} placeholders in template with context values."""
    try:
        return template.format(**{k: (v if v is not None else "") for k, v in context.items()})
    except KeyError:
        return template


async def evaluate_rules_async(
    rules: list[dict],
    context: dict[str, Any],
    llm_client: Any | None = None,
    hardcoded_handler: Callable[[dict, dict[str, Any]], Awaitable[dict | None]] | None = None,
) -> list[dict]:
    """
    Evaluate rules asynchronously. Supports expression, llm, and hardcoded modes.

    Returns list of triggered rules with: rule_id, trigger, action_target, is_blocking,
    severity, action_type, field_ref, action_required, breaks_completeness,
    evaluation_mode, evaluation_log.
    For LLM rules, trigger is the justification from Claude.
    """
    triggered: list[dict] = []
    eval_log: list[dict] = []
    llm_rules: list[tuple[int, dict]] = []
    hardcoded_rules: list[tuple[int, dict]] = []
    skipped = 0

    for idx, rule in enumerate(rules):
        rule_id = rule.get("rule_id", f"unknown-{idx}")
        if not rule.get("enabled", True):
            skipped += 1
            continue
        mode = rule.get("evaluation_mode", "expression")

        if mode == "expression":
            expr = rule.get("condition_expr")
            if not expr:
                eval_log.append({"rule_id": rule_id, "mode": mode, "result": "skipped", "reason": "no_expression"})
                continue
            fired = evaluate_expression(expr, context)
            eval_log.append({"rule_id": rule_id, "mode": mode, "result": "triggered" if fired else "passed"})
            if fired:
                trigger = _format_template(
                    rule.get("trigger_template", ""),
                    context,
                )
                triggered.append({
                    "rule_id": rule_id,
                    "trigger": trigger,
                    "action_target": rule.get("action_target"),
                    "is_blocking": rule.get("is_blocking", True),
                    "severity": rule.get("severity", "high"),
                    "action_type": rule.get("action_type", "escalate"),
                    "field_ref": rule.get("field_ref"),
                    "action_required": rule.get("action_required"),
                    "breaks_completeness": rule.get("breaks_completeness", False),
                    "evaluation_mode": "expression",
                })
        elif mode == "llm":
            llm_rules.append((idx, rule))
        elif mode == "hardcoded" and hardcoded_handler:
            hardcoded_rules.append((idx, rule))

    # Evaluate LLM rules in parallel (capped)
    if llm_client and llm_rules:
        sem = asyncio.Semaphore(MAX_CONCURRENT_LLM)

        async def eval_one(item: tuple[int, dict]) -> dict | None:
            idx, rule = item
            async with sem:
                return await _eval_llm_rule(rule, context, llm_client)

        results = await asyncio.gather(
            *[eval_one(item) for item in llm_rules],
            return_exceptions=True,
        )
        for i, res in enumerate(results):
            llm_rule_id = llm_rules[i][1].get("rule_id", "?")
            if isinstance(res, Exception):
                logger.warning("LLM rule %s evaluation failed: %s", llm_rule_id, res)
                eval_log.append({"rule_id": llm_rule_id, "mode": "llm", "result": "error", "error": str(res)})
                continue
            if res:
                triggered.append(res)
                eval_log.append({"rule_id": llm_rule_id, "mode": "llm", "result": "triggered",
                                 "confidence": res.get("llm_confidence")})
            else:
                eval_log.append({"rule_id": llm_rule_id, "mode": "llm", "result": "passed"})
    elif llm_rules:
        for _, rule in llm_rules:
            eval_log.append({"rule_id": rule.get("rule_id", "?"), "mode": "llm",
                             "result": "skipped", "reason": "no_llm_client"})

    # Hardcoded rules: caller provides handler
    if hardcoded_handler:
        for idx, rule in hardcoded_rules:
            hc_rule_id = rule.get("rule_id", "?")
            result = await hardcoded_handler(rule, context)
            if result:
                triggered.append(result)
                eval_log.append({"rule_id": hc_rule_id, "mode": "hardcoded", "result": "triggered"})
            else:
                eval_log.append({"rule_id": hc_rule_id, "mode": "hardcoded", "result": "passed"})

    triggered_ids = [t["rule_id"] for t in triggered]
    logger.info(
        "Rule evaluation: %d rules, %d skipped, %d triggered %s",
        len(rules), skipped, len(triggered), triggered_ids,
    )

    # Attach evaluation log to each triggered rule for downstream audit
    for t in triggered:
        t["_eval_log"] = eval_log

    return triggered


async def _eval_llm_rule(
    rule: dict,
    context: dict[str, Any],
    llm_client: Any,
) -> dict | None:
    """Evaluate a single LLM rule. Returns triggered dict or None."""
    from app.models.pipeline_io import LLMRuleResult

    import time as _time

    prompt = rule.get("llm_prompt")
    if not prompt:
        return None

    rule_id = rule.get("rule_id", "")
    context_text = "\n".join(f"{k}: {v}" for k, v in sorted(context.items()) if v is not None)

    t0 = _time.monotonic()
    try:
        result, fallback = await llm_client.structured_call(
            system_prompt=prompt,
            user_prompt=f"Context:\n{context_text}",
            response_model=LLMRuleResult,
            max_tokens=500,
        )
        latency_ms = int((_time.monotonic() - t0) * 1000)
        if fallback or result is None or not result.triggered:
            logger.info("LLM rule %s: not triggered (latency=%dms, fallback=%s)",
                        rule_id, latency_ms, fallback)
            return None
        logger.info("LLM rule %s: triggered (confidence=%.2f, latency=%dms)",
                    rule_id, result.confidence, latency_ms)
        return {
            "rule_id": rule_id,
            "trigger": result.justification,
            "action_target": rule.get("action_target"),
            "is_blocking": rule.get("is_blocking", True),
            "severity": rule.get("severity", "high"),
            "action_type": rule.get("action_type", "escalate"),
            "field_ref": rule.get("field_ref"),
            "action_required": rule.get("action_required"),
            "breaks_completeness": rule.get("breaks_completeness", False),
            "evaluation_mode": "llm",
            "llm_confidence": result.confidence,
            "llm_latency_ms": latency_ms,
            "llm_justification": result.justification,
        }
    except Exception as exc:
        latency_ms = int((_time.monotonic() - t0) * 1000)
        logger.warning("LLM rule %s failed after %dms: %s", rule_id, latency_ms, exc)
        return None
