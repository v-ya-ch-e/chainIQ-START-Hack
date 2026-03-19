"""Dynamic rule evaluation engine.

Evaluates rules fetched from the organisational layer against a context dict.
Supports five eval_types: compare, required, threshold, set_membership, custom_llm.
"""

from __future__ import annotations

import logging
import re
from typing import Any, TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from app.clients.llm import LLMClient

logger = logging.getLogger(__name__)


class RuleResult(BaseModel):
    """Outcome of evaluating a single dynamic rule."""

    rule_id: str
    rule_name: str = ""
    eval_type: str = ""
    result: str = "passed"  # passed | failed | warned | skipped | error
    actual_values: dict[str, Any] = Field(default_factory=dict)
    expected_values: dict[str, Any] = Field(default_factory=dict)
    message: str = ""
    action: str = "none"  # exclude | warn | escalate | info | none
    severity: str = "medium"
    is_blocking: bool = False
    escalation_target: str | None = None
    rule_version: int = 1


OPERATORS = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class RuleEngine:
    """Evaluate dynamic rules against a flat context dict."""

    def __init__(self, llm_client: "LLMClient | None" = None):
        self.llm_client = llm_client

    async def evaluate_rules(
        self,
        rules: list[dict],
        context: dict[str, Any],
    ) -> list[RuleResult]:
        results: list[RuleResult] = []
        for rule in sorted(rules, key=lambda r: r.get("priority", 100)):
            if not rule.get("is_active", True):
                continue
            try:
                result = await self._evaluate_one(rule, context)
            except Exception as exc:
                logger.warning("Rule %s evaluation error: %s", rule.get("rule_id"), exc)
                result = RuleResult(
                    rule_id=rule.get("rule_id", "?"),
                    rule_name=rule.get("rule_name", ""),
                    eval_type=rule.get("eval_type", ""),
                    result="error",
                    message=str(exc),
                    rule_version=rule.get("version", 1),
                )
            results.append(result)
        return results

    async def _evaluate_one(self, rule: dict, context: dict) -> RuleResult:
        eval_type = rule.get("eval_type", "")
        config = rule.get("eval_config", {})
        if isinstance(config, str):
            import json
            config = json.loads(config)

        base = dict(
            rule_id=rule.get("rule_id", "?"),
            rule_name=rule.get("rule_name", ""),
            eval_type=eval_type,
            severity=rule.get("severity", "medium"),
            is_blocking=rule.get("is_blocking", False),
            escalation_target=rule.get("escalation_target"),
            rule_version=rule.get("version", 1),
        )

        if eval_type == "compare":
            return self._eval_compare(config, context, rule, base)
        elif eval_type == "required":
            return self._eval_required(config, context, rule, base)
        elif eval_type == "threshold":
            return self._eval_threshold(config, context, rule, base)
        elif eval_type == "set_membership":
            return self._eval_set_membership(config, context, rule, base)
        elif eval_type == "custom_llm":
            return await self._eval_custom_llm(config, context, rule, base)
        else:
            return RuleResult(**base, result="skipped", message=f"Unknown eval_type: {eval_type}")

    # ── Condition checking ─────────────────────────────────────

    def _check_condition(self, condition: dict | None, context: dict) -> bool:
        """Return True if the rule's precondition is met (or no condition exists)."""
        if condition is None:
            return True

        field = condition.get("field")
        op = condition.get("operator", "==")
        expected = condition.get("equals", condition.get("value"))

        if op == "==" and "equals" in condition:
            op = "=="
            expected = condition["equals"]

        actual = context.get(field)

        op_fn = OPERATORS.get(op)
        if op_fn is None:
            return True

        try:
            result = op_fn(actual, expected)
        except (TypeError, ValueError):
            return False

        and_cond = condition.get("and")
        if and_cond and result:
            return self._check_condition(and_cond, context)

        return result

    # ── Message formatting ─────────────────────────────────────

    def _format_message(self, template: str | None, context: dict) -> str:
        if not template:
            return ""
        try:
            return template.format_map(_SafeFormatDict(context))
        except Exception:
            return template

    # ── Evaluators ─────────────────────────────────────────────

    def _eval_compare(self, config: dict, context: dict, rule: dict, base: dict) -> RuleResult:
        condition = config.get("condition")
        if not self._check_condition(condition, context):
            return RuleResult(**base, result="skipped", message="Precondition not met")

        left_field = config.get("left_field", "")
        operator = config.get("operator", "==")
        right_field = config.get("right_field")
        right_constant = config.get("right_constant")

        left_val = context.get(left_field)

        if right_field:
            right_val = context.get(right_field)
        else:
            right_val = right_constant

        if left_val is None or right_val is None:
            return RuleResult(
                **base, result="skipped",
                message=f"Cannot compare: {left_field}={left_val}, right={right_val}",
                actual_values={left_field: left_val},
                expected_values={"right": right_val},
            )

        op_fn = OPERATORS.get(operator)
        if op_fn is None:
            return RuleResult(**base, result="error", message=f"Unknown operator: {operator}")

        try:
            passed = op_fn(left_val, right_val)
        except (TypeError, ValueError) as e:
            return RuleResult(**base, result="error", message=str(e))

        action_on_fail = rule.get("action_on_fail", "warn")
        template = rule.get("fail_message_template")

        if passed:
            return RuleResult(
                **base, result="passed",
                actual_values={left_field: left_val},
                expected_values={right_field or "constant": right_val},
            )
        else:
            msg = self._format_message(template, context) or (
                f"{left_field}={left_val} {operator} {right_val} is false"
            )
            return RuleResult(
                **base, result="failed",
                action=action_on_fail,
                message=msg,
                actual_values={left_field: left_val},
                expected_values={right_field or "constant": right_val},
            )

    def _eval_required(self, config: dict, context: dict, rule: dict, base: dict) -> RuleResult:
        fields = config.get("fields", [])
        missing = []
        for f in fields:
            name = f.get("name", f) if isinstance(f, dict) else f
            val = context.get(name)
            is_missing = val is None or (isinstance(val, (list, str)) and len(val) == 0)
            if is_missing:
                missing.append(f if isinstance(f, dict) else {"name": name, "severity": "high"})

        if not missing:
            return RuleResult(**base, result="passed", message="All required fields present")

        action_on_fail = rule.get("action_on_fail", "warn")
        template = rule.get("fail_message_template", "")
        names = [m["name"] if isinstance(m, dict) else m for m in missing]
        msg = f"Missing fields: {', '.join(names)}"
        if template:
            msg = "; ".join(
                self._format_message(template, {**context, "field_name": n})
                for n in names
            )

        max_sev = "low"
        sev_order = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        for m in missing:
            s = m.get("severity", "medium") if isinstance(m, dict) else "medium"
            if sev_order.get(s, 0) > sev_order.get(max_sev, 0):
                max_sev = s

        return RuleResult(
            **{**base, "severity": max_sev},
            result="failed",
            action=action_on_fail,
            message=msg,
            actual_values={"missing": names},
        )

    def _eval_threshold(self, config: dict, context: dict, rule: dict, base: dict) -> RuleResult:
        condition = config.get("condition")
        if not self._check_condition(condition, context):
            return RuleResult(**base, result="skipped", message="Precondition not met")

        field = config.get("field", "")
        val = context.get(field)
        if val is None:
            return RuleResult(**base, result="skipped", message=f"{field} is null")

        try:
            val = float(val)
        except (TypeError, ValueError):
            return RuleResult(**base, result="error", message=f"{field}={val} is not numeric")

        min_val = config.get("min")
        max_val = config.get("max")

        if min_val is not None and val < float(min_val):
            msg = self._format_message(rule.get("fail_message_template"), context) or (
                f"{field}={val} is below minimum {min_val}"
            )
            return RuleResult(
                **base, result="failed",
                action=rule.get("action_on_fail", "warn"),
                message=msg,
                actual_values={field: val},
                expected_values={"min": min_val, "max": max_val},
            )

        if max_val is not None and val > float(max_val):
            msg = self._format_message(rule.get("fail_message_template"), context) or (
                f"{field}={val} exceeds maximum {max_val}"
            )
            return RuleResult(
                **base, result="failed",
                action=rule.get("action_on_fail", "warn"),
                message=msg,
                actual_values={field: val},
                expected_values={"min": min_val, "max": max_val},
            )

        return RuleResult(
            **base, result="passed",
            actual_values={field: val},
            expected_values={"min": min_val, "max": max_val},
        )

    def _eval_set_membership(self, config: dict, context: dict, rule: dict, base: dict) -> RuleResult:
        field = config.get("field", "")
        set_field = config.get("set_field", "")
        expected_in_set = config.get("expected_in_set", True)

        val = context.get(field)
        the_set = context.get(set_field, [])

        if val is None:
            return RuleResult(**base, result="skipped", message=f"{field} is null")

        if not isinstance(the_set, (list, set, tuple)):
            the_set = []

        is_in_set = val in the_set

        if is_in_set == expected_in_set:
            return RuleResult(
                **base, result="passed",
                actual_values={field: val, "in_set": is_in_set},
            )
        else:
            msg = self._format_message(rule.get("fail_message_template"), context) or (
                f"{field}={val} {'not ' if expected_in_set else ''}in {set_field}"
            )
            return RuleResult(
                **base, result="failed",
                action=rule.get("action_on_fail", "warn"),
                message=msg,
                actual_values={field: val, "in_set": is_in_set},
                expected_values={"expected_in_set": expected_in_set},
            )

    async def _eval_custom_llm(self, config: dict, context: dict, rule: dict, base: dict) -> RuleResult:
        if self.llm_client is None:
            return RuleResult(**base, result="skipped", message="No LLM client available")

        system_prompt = config.get("system_prompt", "")
        user_template = config.get("user_prompt_template", "")
        input_fields = config.get("input_fields", [])
        max_tokens = config.get("max_tokens", 1000)

        prompt_context = {k: context.get(k) for k in input_fields}
        user_prompt = self._format_message(user_template, prompt_context)

        class LLMRuleResponse(BaseModel):
            verdict: str = "pass"
            issues: list[dict] = Field(default_factory=list)
            explanation: str = ""

        try:
            result, fallback = await self.llm_client.structured_call(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                response_model=LLMRuleResponse,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            return RuleResult(**base, result="error", message=f"LLM call failed: {exc}")

        if fallback or result is None:
            return RuleResult(**base, result="skipped", message="LLM call failed; skipping rule")

        pass_when = config.get("pass_when", "verdict == 'pass'")
        if pass_when == "no_contradictions":
            passed = len(result.issues) == 0
        else:
            passed = result.verdict.lower() in ("pass", "passed", "ok")

        if passed:
            return RuleResult(
                **base, result="passed",
                message=result.explanation or "LLM check passed",
                actual_values={"verdict": result.verdict},
            )
        else:
            msg = self._format_message(rule.get("fail_message_template"), context) or result.explanation
            return RuleResult(
                **base, result="failed",
                action=rule.get("action_on_fail", "warn"),
                message=msg,
                actual_values={"verdict": result.verdict, "issues": [i for i in result.issues]},
            )


class _SafeFormatDict(dict):
    """Dict subclass that returns {key} for missing keys instead of raising KeyError."""

    def __missing__(self, key):
        return f"{{{key}}}"
