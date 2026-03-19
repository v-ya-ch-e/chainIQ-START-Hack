"""Synchronous rule evaluator using simpleeval for expression-based rules."""

from __future__ import annotations

import logging
from typing import Any

from simpleeval import SimpleEval

logger = logging.getLogger(__name__)


def _safe_context(context: dict[str, Any]) -> dict[str, Any]:
    """Merge context with built-in names needed for expressions (None, True, False)."""
    base = {"None": None, "True": True, "False": False}
    return {**base, **context}


def evaluate_expression(condition_expr: str, context: dict[str, Any]) -> bool:
    """
    Safely evaluate a Python expression against a context dict using simpleeval.

    Uses explicit names=context — no builtins, no imports. Returns False on error.
    """
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


def evaluate_rules(
    rules: list[dict],
    context: dict[str, Any],
) -> list[dict]:
    """
    Evaluate a list of rules against a context. Returns triggered rules with
    formatted trigger messages.

    Each rule dict must have: rule_id, evaluation_mode, condition_expr (for expression),
    trigger_template, action_target, is_blocking, severity.
    """
    triggered: list[dict] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        mode = rule.get("evaluation_mode", "expression")
        if mode == "hardcoded":
            continue  # Handled by caller
        if mode == "llm":
            continue  # Handled by Logical Layer async evaluator
        expr = rule.get("condition_expr")
        if not expr:
            continue
        if evaluate_expression(expr, context):
            trigger = _format_template(
                rule.get("trigger_template", ""),
                context,
            )
            triggered.append({
                "rule_id": rule.get("rule_id", ""),
                "trigger": trigger,
                "action_target": rule.get("action_target"),
                "is_blocking": rule.get("is_blocking", True),
                "severity": rule.get("severity", "high"),
            })
    return triggered


def _format_template(template: str, context: dict[str, Any]) -> str:
    """Replace {field} placeholders in template with context values."""
    try:
        return template.format(**{k: (v if v is not None else "") for k, v in context.items()})
    except KeyError:
        return template
