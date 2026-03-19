from datetime import datetime
import unittest

try:
    from app.services.escalations import (
        EscalationRuleInput,
        compute_escalations_for_rule_input,
    )
    IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - environment dependent
    EscalationRuleInput = None  # type: ignore[assignment]
    compute_escalations_for_rule_input = None  # type: ignore[assignment]
    IMPORT_ERROR = exc


RULE_LABELS = {
    "ER-001": "missing_required_information",
    "ER-002": "preferred_supplier_restricted",
    "ER-003": "value_exceeds_threshold",
    "ER-004": "no_compliant_supplier_found",
    "ER-005": "data_residency_constraint_conflict",
    "ER-006": "single_supplier_capacity_risk",
    "ER-007": "brand_safety_review_needed",
    "ER-008": "supplier_not_registered",
}

RULE_TARGETS = {
    "ER-001": "Requester Clarification",
    "ER-002": "Procurement Manager",
    "ER-003": "Head of Strategic Sourcing",
    "ER-004": "Head of Category",
    "ER-005": "Security and Compliance Review",
    "ER-006": "Sourcing Excellence Lead",
    "ER-007": "Marketing Governance Lead",
    "ER-008": "Regional Compliance Lead",
}


def make_rule_input(**overrides) -> EscalationRuleInput:
    if EscalationRuleInput is None:  # pragma: no cover - environment dependent
        raise RuntimeError("EscalationRuleInput import unavailable")

    base = EscalationRuleInput(
        request_id="REQ-TEST",
        title="Test request",
        created_at=datetime(2026, 3, 19, 10, 0, 0),
        business_unit="IT",
        country_scope="DE",
        category_label="IT / Laptops",
        request_status="pending_review",
        request_text="Need competitive quotes from approved suppliers.",
        request_currency="EUR",
        missing_required_information=False,
        preferred_supplier_restricted=False,
        has_compliant_priceable_supplier=True,
        has_residency_compatible_supplier=None,
        single_supplier_capacity_risk=False,
        preferred_supplier_unregistered_usd=False,
        threshold_id=None,
        threshold_quotes_required=1,
        threshold_managers=[],
        threshold_deviation_approvers=[],
    )
    for field, value in overrides.items():
        setattr(base, field, value)
    return base


class EscalationServiceTests(unittest.TestCase):
    def setUp(self):
        if IMPORT_ERROR is not None:
            self.skipTest(f"Backend dependencies unavailable: {IMPORT_ERROR}")

    def test_missing_info_triggers_er001(self):
        result = compute_escalations_for_rule_input(
            make_rule_input(missing_required_information=True),
            RULE_LABELS,
            RULE_TARGETS,
        )
        self.assertIn("ER-001", {entry.rule_id for entry in result})

    def test_preferred_restricted_triggers_er002(self):
        result = compute_escalations_for_rule_input(
            make_rule_input(preferred_supplier_restricted=True),
            RULE_LABELS,
            RULE_TARGETS,
        )
        self.assertIn("ER-002", {entry.rule_id for entry in result})

    def test_no_compliant_supplier_triggers_er004(self):
        result = compute_escalations_for_rule_input(
            make_rule_input(has_compliant_priceable_supplier=False),
            RULE_LABELS,
            RULE_TARGETS,
        )
        self.assertIn("ER-004", {entry.rule_id for entry in result})

    def test_data_residency_conflict_triggers_er005(self):
        result = compute_escalations_for_rule_input(
            make_rule_input(has_residency_compatible_supplier=False),
            RULE_LABELS,
            RULE_TARGETS,
        )
        self.assertIn("ER-005", {entry.rule_id for entry in result})

    def test_influencer_category_triggers_er007(self):
        result = compute_escalations_for_rule_input(
            make_rule_input(category_label="Marketing / Influencer Campaign Management"),
            RULE_LABELS,
            RULE_TARGETS,
        )
        self.assertIn("ER-007", {entry.rule_id for entry in result})

    def test_quote_policy_conflict_triggers_at_row(self):
        result = compute_escalations_for_rule_input(
            make_rule_input(
                request_text="Single supplier only, no exception.",
                threshold_id="AT-002",
                threshold_quotes_required=2,
                threshold_deviation_approvers=["Procurement Manager"],
            ),
            RULE_LABELS,
            RULE_TARGETS,
        )
        rule_ids = {entry.rule_id for entry in result}
        self.assertIn("AT-002", rule_ids)


if __name__ == "__main__":
    unittest.main()
