"""Unit tests for the dynamic rule engine.

Tests all 5 eval_types: compare, required, threshold, set_membership, custom_llm.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.pipeline.rule_engine import RuleEngine, RuleResult


def _rule(eval_type="compare", eval_config=None, **overrides):
    """Helper to build a minimal rule dict."""
    base = {
        "rule_id": "TEST-001",
        "rule_name": "Test Rule",
        "eval_type": eval_type,
        "eval_config": eval_config or {},
        "action_on_fail": "warn",
        "severity": "high",
        "is_blocking": False,
        "escalation_target": None,
        "fail_message_template": None,
        "is_active": True,
        "priority": 100,
        "version": 1,
    }
    base.update(overrides)
    return base


# ── Compare evaluator ──────────────────────────────────────────────


class TestCompareEvaluator:
    @pytest.mark.asyncio
    async def test_field_gte_field_passes(self):
        engine = RuleEngine()
        rule = _rule(eval_config={
            "left_field": "budget_amount",
            "operator": ">=",
            "right_field": "total_price",
        })
        ctx = {"budget_amount": 50000, "total_price": 40000}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_field_gte_field_fails(self):
        engine = RuleEngine()
        rule = _rule(eval_config={
            "left_field": "budget_amount",
            "operator": ">=",
            "right_field": "total_price",
        }, action_on_fail="exclude")
        ctx = {"budget_amount": 30000, "total_price": 40000}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"
        assert results[0].action == "exclude"

    @pytest.mark.asyncio
    async def test_field_eq_constant(self):
        engine = RuleEngine()
        rule = _rule(eval_config={
            "left_field": "is_restricted",
            "operator": "==",
            "right_constant": False,
        })
        ctx = {"is_restricted": False}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_field_eq_constant_fails(self):
        engine = RuleEngine()
        rule = _rule(eval_config={
            "left_field": "is_restricted",
            "operator": "==",
            "right_constant": False,
        }, action_on_fail="exclude")
        ctx = {"is_restricted": True}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"

    @pytest.mark.asyncio
    async def test_with_condition_met(self):
        engine = RuleEngine()
        rule = _rule(eval_config={
            "left_field": "data_residency_supported",
            "operator": "==",
            "right_constant": True,
            "condition": {"field": "data_residency_constraint", "operator": "==", "value": True},
        })
        ctx = {"data_residency_constraint": True, "data_residency_supported": True}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_with_condition_not_met_skips(self):
        engine = RuleEngine()
        rule = _rule(eval_config={
            "left_field": "data_residency_supported",
            "operator": "==",
            "right_constant": True,
            "condition": {"field": "data_residency_constraint", "operator": "==", "value": True},
        })
        ctx = {"data_residency_constraint": False, "data_residency_supported": False}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "skipped"

    @pytest.mark.asyncio
    async def test_null_left_skips(self):
        engine = RuleEngine()
        rule = _rule(eval_config={
            "left_field": "budget_amount",
            "operator": ">=",
            "right_constant": 100,
        })
        ctx = {"budget_amount": None}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "skipped"

    @pytest.mark.asyncio
    async def test_all_operators(self):
        engine = RuleEngine()
        tests = [
            ("<", 5, 10, "passed"),
            ("<", 10, 5, "failed"),
            ("<=", 5, 5, "passed"),
            (">", 10, 5, "passed"),
            (">", 5, 10, "failed"),
            ("!=", 5, 10, "passed"),
            ("!=", 5, 5, "failed"),
        ]
        for op, left, right, expected in tests:
            rule = _rule(eval_config={
                "left_field": "val",
                "operator": op,
                "right_constant": right,
            })
            results = await engine.evaluate_rules([rule], {"val": left})
            assert results[0].result == expected, f"{left} {op} {right} should be {expected}"

    @pytest.mark.asyncio
    async def test_message_template(self):
        engine = RuleEngine()
        rule = _rule(
            eval_config={
                "left_field": "quantity",
                "operator": "<=",
                "right_field": "capacity",
            },
            fail_message_template="Quantity {quantity} exceeds capacity {capacity}",
        )
        ctx = {"quantity": 500, "capacity": 100}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"
        assert "500" in results[0].message
        assert "100" in results[0].message

    @pytest.mark.asyncio
    async def test_nested_and_condition(self):
        engine = RuleEngine()
        rule = _rule(eval_config={
            "left_field": "budget_amount",
            "operator": ">=",
            "right_field": "min_total_price",
            "condition": {
                "field": "budget_amount", "operator": "!=", "value": None,
                "and": {"field": "min_total_price", "operator": "!=", "value": None},
            },
        })
        ctx = {"budget_amount": None, "min_total_price": 100}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "skipped"


# ── Required evaluator ─────────────────────────────────────────────


class TestRequiredEvaluator:
    @pytest.mark.asyncio
    async def test_all_present(self):
        engine = RuleEngine()
        rule = _rule(eval_type="required", eval_config={
            "fields": [
                {"name": "category_l1", "severity": "critical"},
                {"name": "currency", "severity": "critical"},
            ]
        })
        ctx = {"category_l1": "IT", "currency": "EUR"}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_missing_field(self):
        engine = RuleEngine()
        rule = _rule(eval_type="required", eval_config={
            "fields": [
                {"name": "category_l1", "severity": "critical"},
                {"name": "currency", "severity": "critical"},
            ]
        })
        ctx = {"category_l1": "IT", "currency": None}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"
        assert "currency" in results[0].actual_values.get("missing", [])

    @pytest.mark.asyncio
    async def test_empty_string_is_missing(self):
        engine = RuleEngine()
        rule = _rule(eval_type="required", eval_config={
            "fields": [{"name": "category_l1", "severity": "critical"}]
        })
        ctx = {"category_l1": ""}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"

    @pytest.mark.asyncio
    async def test_empty_list_is_missing(self):
        engine = RuleEngine()
        rule = _rule(eval_type="required", eval_config={
            "fields": [{"name": "delivery_countries", "severity": "high"}]
        })
        ctx = {"delivery_countries": []}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"

    @pytest.mark.asyncio
    async def test_severity_propagation(self):
        engine = RuleEngine()
        rule = _rule(eval_type="required", eval_config={
            "fields": [
                {"name": "a", "severity": "low"},
                {"name": "b", "severity": "critical"},
            ]
        })
        ctx = {"a": None, "b": None}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].severity == "critical"

    @pytest.mark.asyncio
    async def test_message_template(self):
        engine = RuleEngine()
        rule = _rule(
            eval_type="required",
            eval_config={"fields": [{"name": "budget_amount", "severity": "high"}]},
            fail_message_template="{field_name} is missing",
        )
        ctx = {"budget_amount": None}
        results = await engine.evaluate_rules([rule], ctx)
        assert "budget_amount" in results[0].message


# ── Threshold evaluator ────────────────────────────────────────────


class TestThresholdEvaluator:
    @pytest.mark.asyncio
    async def test_within_bounds(self):
        engine = RuleEngine()
        rule = _rule(eval_type="threshold", eval_config={
            "field": "risk_score", "min": 0, "max": 30,
        })
        ctx = {"risk_score": 15}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_above_max(self):
        engine = RuleEngine()
        rule = _rule(eval_type="threshold", eval_config={
            "field": "risk_score", "min": None, "max": 30,
        }, action_on_fail="exclude")
        ctx = {"risk_score": 45}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"
        assert results[0].action == "exclude"

    @pytest.mark.asyncio
    async def test_below_min(self):
        engine = RuleEngine()
        rule = _rule(eval_type="threshold", eval_config={
            "field": "score", "min": 10, "max": None,
        })
        ctx = {"score": 5}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"

    @pytest.mark.asyncio
    async def test_at_boundary(self):
        engine = RuleEngine()
        rule = _rule(eval_type="threshold", eval_config={
            "field": "score", "min": 0, "max": 30,
        })
        ctx = {"score": 30}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_with_condition_met(self):
        engine = RuleEngine()
        rule = _rule(eval_type="threshold", eval_config={
            "field": "risk_score", "min": None, "max": 30,
            "condition": {"field": "preferred_supplier", "operator": "==", "value": False},
        })
        ctx = {"risk_score": 45, "preferred_supplier": False}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"

    @pytest.mark.asyncio
    async def test_with_condition_not_met_skips(self):
        engine = RuleEngine()
        rule = _rule(eval_type="threshold", eval_config={
            "field": "risk_score", "min": None, "max": 30,
            "condition": {"field": "preferred_supplier", "operator": "==", "value": False},
        })
        ctx = {"risk_score": 45, "preferred_supplier": True}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "skipped"

    @pytest.mark.asyncio
    async def test_null_field_skips(self):
        engine = RuleEngine()
        rule = _rule(eval_type="threshold", eval_config={
            "field": "risk_score", "min": 0, "max": 30,
        })
        ctx = {"risk_score": None}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "skipped"

    @pytest.mark.asyncio
    async def test_non_numeric_field_errors(self):
        engine = RuleEngine()
        rule = _rule(eval_type="threshold", eval_config={
            "field": "risk_score", "min": 0, "max": 30,
        })
        ctx = {"risk_score": "not_a_number"}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "error"


# ── Set membership evaluator ───────────────────────────────────────


class TestSetMembershipEvaluator:
    @pytest.mark.asyncio
    async def test_in_set_when_expected(self):
        engine = RuleEngine()
        rule = _rule(eval_type="set_membership", eval_config={
            "field": "category_l2",
            "set_field": "matching_categories",
            "expected_in_set": True,
        })
        ctx = {"category_l2": "Laptops", "matching_categories": ["Laptops", "Tablets"]}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_not_in_set_when_expected(self):
        engine = RuleEngine()
        rule = _rule(eval_type="set_membership", eval_config={
            "field": "category_l2",
            "set_field": "matching_categories",
            "expected_in_set": True,
        })
        ctx = {"category_l2": "Monitors", "matching_categories": ["Laptops", "Tablets"]}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"

    @pytest.mark.asyncio
    async def test_not_in_set_when_expected_not(self):
        engine = RuleEngine()
        rule = _rule(eval_type="set_membership", eval_config={
            "field": "supplier_id",
            "set_field": "restricted_ids",
            "expected_in_set": False,
        })
        ctx = {"supplier_id": "SUP-0001", "restricted_ids": ["SUP-0008", "SUP-0011"]}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_in_set_when_expected_not(self):
        engine = RuleEngine()
        rule = _rule(eval_type="set_membership", eval_config={
            "field": "supplier_id",
            "set_field": "restricted_ids",
            "expected_in_set": False,
        }, action_on_fail="exclude")
        ctx = {"supplier_id": "SUP-0008", "restricted_ids": ["SUP-0008", "SUP-0011"]}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"
        assert results[0].action == "exclude"

    @pytest.mark.asyncio
    async def test_null_field_skips(self):
        engine = RuleEngine()
        rule = _rule(eval_type="set_membership", eval_config={
            "field": "supplier_id",
            "set_field": "restricted_ids",
            "expected_in_set": False,
        })
        ctx = {"supplier_id": None, "restricted_ids": ["SUP-0008"]}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "skipped"

    @pytest.mark.asyncio
    async def test_empty_set(self):
        engine = RuleEngine()
        rule = _rule(eval_type="set_membership", eval_config={
            "field": "supplier_id",
            "set_field": "restricted_ids",
            "expected_in_set": False,
        })
        ctx = {"supplier_id": "SUP-0001", "restricted_ids": []}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"


# ── Custom LLM evaluator ──────────────────────────────────────────


class TestCustomLLMEvaluator:
    @pytest.mark.asyncio
    async def test_no_llm_client_skips(self):
        engine = RuleEngine(llm_client=None)
        rule = _rule(eval_type="custom_llm", eval_config={
            "system_prompt": "test",
            "user_prompt_template": "test {request_text}",
            "input_fields": ["request_text"],
            "pass_when": "verdict == 'pass'",
        })
        ctx = {"request_text": "Buy laptops"}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "skipped"

    @pytest.mark.asyncio
    async def test_llm_pass(self):
        mock_llm = MagicMock()

        class FakeResponse:
            verdict = "pass"
            issues = []
            explanation = "No issues found"

        mock_llm.structured_call = AsyncMock(return_value=(FakeResponse(), False))
        engine = RuleEngine(llm_client=mock_llm)

        rule = _rule(eval_type="custom_llm", eval_config={
            "system_prompt": "Check for issues",
            "user_prompt_template": "Text: {request_text}",
            "input_fields": ["request_text"],
            "pass_when": "verdict == 'pass'",
            "max_tokens": 500,
        })
        ctx = {"request_text": "Buy 100 laptops"}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"

    @pytest.mark.asyncio
    async def test_llm_fail(self):
        mock_llm = MagicMock()

        class FakeResponse:
            verdict = "fail"
            issues = [{"type": "contradiction", "description": "Quantity mismatch"}]
            explanation = "Quantity in text differs from field"

        mock_llm.structured_call = AsyncMock(return_value=(FakeResponse(), False))
        engine = RuleEngine(llm_client=mock_llm)

        rule = _rule(eval_type="custom_llm", eval_config={
            "system_prompt": "Check",
            "user_prompt_template": "Text: {request_text}",
            "input_fields": ["request_text"],
            "pass_when": "verdict == 'pass'",
        }, action_on_fail="escalate")
        ctx = {"request_text": "Buy 100 laptops"}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "failed"
        assert results[0].action == "escalate"

    @pytest.mark.asyncio
    async def test_llm_fallback_skips(self):
        mock_llm = MagicMock()
        mock_llm.structured_call = AsyncMock(return_value=(None, True))
        engine = RuleEngine(llm_client=mock_llm)

        rule = _rule(eval_type="custom_llm", eval_config={
            "system_prompt": "Check",
            "user_prompt_template": "Text: {request_text}",
            "input_fields": ["request_text"],
        })
        ctx = {"request_text": "Buy laptops"}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "skipped"

    @pytest.mark.asyncio
    async def test_no_contradictions_pass_when(self):
        mock_llm = MagicMock()

        class FakeResponse:
            verdict = "fail"
            issues = []
            explanation = ""

        mock_llm.structured_call = AsyncMock(return_value=(FakeResponse(), False))
        engine = RuleEngine(llm_client=mock_llm)

        rule = _rule(eval_type="custom_llm", eval_config={
            "system_prompt": "Check",
            "user_prompt_template": "{request_text}",
            "input_fields": ["request_text"],
            "pass_when": "no_contradictions",
        })
        ctx = {"request_text": "ok"}
        results = await engine.evaluate_rules([rule], ctx)
        assert results[0].result == "passed"


# ── Engine-level tests ─────────────────────────────────────────────


class TestEngineLevel:
    @pytest.mark.asyncio
    async def test_inactive_rules_skipped(self):
        engine = RuleEngine()
        rule = _rule(is_active=False, eval_config={
            "left_field": "x", "operator": "==", "right_constant": 1,
        })
        results = await engine.evaluate_rules([rule], {"x": 999})
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_priority_ordering(self):
        engine = RuleEngine()
        r1 = _rule(rule_id="RULE-B", priority=200, eval_config={
            "left_field": "x", "operator": "==", "right_constant": 1,
        })
        r2 = _rule(rule_id="RULE-A", priority=50, eval_config={
            "left_field": "x", "operator": "==", "right_constant": 1,
        })
        results = await engine.evaluate_rules([r1, r2], {"x": 1})
        assert results[0].rule_id == "RULE-A"
        assert results[1].rule_id == "RULE-B"

    @pytest.mark.asyncio
    async def test_unknown_eval_type_skips(self):
        engine = RuleEngine()
        rule = _rule(eval_type="unknown_type", eval_config={})
        results = await engine.evaluate_rules([rule], {})
        assert results[0].result == "skipped"
        assert "Unknown" in results[0].message

    @pytest.mark.asyncio
    async def test_exception_in_evaluator_returns_error(self):
        engine = RuleEngine()
        rule = _rule(eval_config=None)
        rule["eval_config"] = None
        results = await engine.evaluate_rules([rule], {})
        assert results[0].result == "error"

    @pytest.mark.asyncio
    async def test_multiple_rules_all_evaluated(self):
        engine = RuleEngine()
        rules = [
            _rule(rule_id="R1", eval_config={
                "left_field": "a", "operator": ">", "right_constant": 0,
            }),
            _rule(rule_id="R2", eval_type="required", eval_config={
                "fields": [{"name": "b", "severity": "high"}],
            }),
            _rule(rule_id="R3", eval_type="threshold", eval_config={
                "field": "c", "min": 0, "max": 100,
            }),
        ]
        ctx = {"a": 5, "b": "present", "c": 50}
        results = await engine.evaluate_rules(rules, ctx)
        assert len(results) == 3
        assert all(r.result == "passed" for r in results)

    @pytest.mark.asyncio
    async def test_json_string_eval_config(self):
        """eval_config can come as a JSON string from the API."""
        import json
        engine = RuleEngine()
        config = json.dumps({
            "left_field": "quantity",
            "operator": ">=",
            "right_constant": 10,
        })
        rule = _rule(eval_config=config)
        results = await engine.evaluate_rules([rule], {"quantity": 20})
        assert results[0].result == "passed"
