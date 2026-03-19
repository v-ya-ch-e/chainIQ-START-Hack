"""
Create dynamic_rules, dynamic_rule_versions, and rule_evaluation_results tables.
Seed all existing procurement rules with proper eval_config.
Run after migrate.py and migrate_rules.py. Idempotent — uses CREATE TABLE IF NOT EXISTS
and INSERT IGNORE.
"""

import json
import os
import sys
import uuid
from datetime import datetime

import mysql.connector
from dotenv import load_dotenv

load_dotenv()


def get_connection():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
    )


def create_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_rules (
          rule_id             VARCHAR(20)  NOT NULL,
          rule_name           VARCHAR(200) NOT NULL,
          description         TEXT         NULL,
          rule_category       VARCHAR(20)  NOT NULL,
          eval_type           VARCHAR(20)  NOT NULL,
          scope               VARCHAR(10)  NOT NULL DEFAULT 'request',
          pipeline_stage      VARCHAR(20)  NOT NULL,
          eval_config         JSON         NOT NULL,
          action_on_fail      VARCHAR(20)  NOT NULL DEFAULT 'warn',
          severity            VARCHAR(10)  NOT NULL DEFAULT 'medium',
          is_blocking         BOOLEAN      NOT NULL DEFAULT FALSE,
          escalation_target   VARCHAR(200) NULL,
          fail_message_template TEXT       NULL,
          is_active           BOOLEAN      NOT NULL DEFAULT TRUE,
          is_skippable        BOOLEAN      NOT NULL DEFAULT FALSE,
          priority            INT          NOT NULL DEFAULT 100,
          version             INT          NOT NULL DEFAULT 1,
          created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          created_by          VARCHAR(100) NULL,
          PRIMARY KEY (rule_id),
          INDEX idx_dr_stage    (pipeline_stage),
          INDEX idx_dr_active   (is_active),
          INDEX idx_dr_category (rule_category)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dynamic_rule_versions (
          id              INT          AUTO_INCREMENT,
          rule_id         VARCHAR(20)  NOT NULL,
          version         INT          NOT NULL,
          snapshot        JSON         NOT NULL,
          valid_from      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          valid_to        DATETIME     NULL,
          changed_by      VARCHAR(100) NULL,
          change_reason   TEXT         NULL,
          PRIMARY KEY (id),
          UNIQUE KEY uq_drv (rule_id, version),
          INDEX idx_drv_rule (rule_id),
          CONSTRAINT fk_drv_rule FOREIGN KEY (rule_id)
            REFERENCES dynamic_rules(rule_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rule_evaluation_results (
          result_id       CHAR(36)     NOT NULL,
          run_id          CHAR(36)     NOT NULL,
          rule_id         VARCHAR(20)  NOT NULL,
          rule_version    INT          NOT NULL,
          supplier_id     VARCHAR(10)  NULL,
          scope           VARCHAR(10)  NOT NULL,
          result          VARCHAR(10)  NOT NULL,
          actual_values   JSON         NULL,
          expected_values JSON         NULL,
          message         TEXT         NULL,
          action_taken    VARCHAR(20)  NULL,
          evaluated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (result_id),
          INDEX idx_rer_run     (run_id),
          INDEX idx_rer_rule    (rule_id),
          INDEX idx_rer_run_rule (run_id, rule_id),
          CONSTRAINT fk_rer_rule FOREIGN KEY (rule_id)
            REFERENCES dynamic_rules(rule_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)


SEED_RULES = [
    # ── Validate stage ──────────────────────────────────────────────
    {
        "rule_id": "VAL-001",
        "rule_name": "Required fields check",
        "description": "Ensure critical request fields are present",
        "rule_category": "hard_rule",
        "eval_type": "required",
        "scope": "request",
        "pipeline_stage": "validate",
        "eval_config": {
            "fields": [
                {"name": "category_l1", "severity": "critical"},
                {"name": "category_l2", "severity": "critical"},
                {"name": "currency", "severity": "critical"},
            ]
        },
        "action_on_fail": "warn",
        "severity": "critical",
        "is_blocking": False,
        "fail_message_template": "Required field {field_name} is missing",
        "priority": 10,
    },
    {
        "rule_id": "VAL-002",
        "rule_name": "Recommended fields check",
        "description": "Flag missing optional fields that degrade pipeline quality",
        "rule_category": "policy_check",
        "eval_type": "required",
        "scope": "request",
        "pipeline_stage": "validate",
        "eval_config": {
            "fields": [
                {"name": "budget_amount", "severity": "high"},
                {"name": "quantity", "severity": "high"},
                {"name": "required_by_date", "severity": "medium"},
                {"name": "delivery_countries", "severity": "high"},
            ]
        },
        "action_on_fail": "warn",
        "severity": "high",
        "is_blocking": False,
        "fail_message_template": "{field_name} is not provided; pipeline will continue with degraded capability",
        "priority": 20,
    },
    {
        "rule_id": "VAL-003",
        "rule_name": "Past delivery date check",
        "description": "Required-by date must not be in the past",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "validate",
        "eval_config": {
            "left_field": "days_until_required",
            "operator": ">=",
            "right_field": None,
            "right_constant": 0,
            "condition": {"field": "days_until_required", "operator": "!=", "value": None},
        },
        "action_on_fail": "warn",
        "severity": "critical",
        "is_blocking": False,
        "fail_message_template": "Required-by date is in the past ({days_until_required} days ago)",
        "priority": 30,
    },
    {
        "rule_id": "VAL-004",
        "rule_name": "Budget sufficiency check",
        "description": "Budget must cover at least the minimum total price across suppliers",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "validate",
        "eval_config": {
            "left_field": "budget_amount",
            "operator": ">=",
            "right_field": "min_total_price",
            "right_constant": None,
            "condition": {
                "field": "budget_amount", "operator": "!=", "value": None,
                "and": {"field": "min_total_price", "operator": "!=", "value": None},
            },
        },
        "action_on_fail": "warn",
        "severity": "critical",
        "is_blocking": False,
        "fail_message_template": "Budget {currency} {budget_amount} cannot cover minimum total {currency} {min_total_price}",
        "priority": 40,
    },
    {
        "rule_id": "VAL-005",
        "rule_name": "Lead time feasibility check",
        "description": "Delivery date must allow enough time for at least one supplier's expedited lead time",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "validate",
        "eval_config": {
            "left_field": "days_until_required",
            "operator": ">=",
            "right_field": "min_expedited_lead_time",
            "right_constant": None,
            "condition": {
                "field": "days_until_required", "operator": "!=", "value": None,
                "and": {"field": "min_expedited_lead_time", "operator": "!=", "value": None},
            },
        },
        "action_on_fail": "warn",
        "severity": "high",
        "is_blocking": False,
        "fail_message_template": "Lead time infeasible: {days_until_required} days available but fastest supplier needs {min_expedited_lead_time} days",
        "priority": 50,
    },
    {
        "rule_id": "VAL-006",
        "rule_name": "Text/field contradiction detection",
        "description": "Use LLM to detect contradictions between request text and structured fields",
        "rule_category": "hard_rule",
        "eval_type": "custom_llm",
        "scope": "request",
        "pipeline_stage": "validate",
        "eval_config": {
            "system_prompt": "You are a procurement validation assistant. Find CONTRADICTIONS between the free-text request and structured fields. Only flag: 'missing_info' and 'contradictory'. Be CONSERVATIVE.",
            "user_prompt_template": "## Structured Fields\nrequest_id: {request_id}\ncategory_l1: {category_l1}\ncategory_l2: {category_l2}\nquantity: {quantity}\nbudget_amount: {budget_amount}\ncurrency: {currency}\nrequired_by_date: {required_by_date}\n\n## Request Text\n{request_text}\n\nFind contradictions and extract any requester instruction.",
            "input_fields": ["request_id", "category_l1", "category_l2", "quantity", "budget_amount", "currency", "required_by_date", "request_text"],
            "pass_when": "no_contradictions",
            "max_tokens": 1500,
        },
        "action_on_fail": "warn",
        "severity": "high",
        "is_blocking": False,
        "is_skippable": True,
        "fail_message_template": "LLM detected contradictions in request",
        "priority": 60,
    },

    # ── Comply stage (supplier-scoped) ──────────────────────────────
    {
        "rule_id": "HR-001",
        "rule_name": "Budget ceiling check",
        "description": "Supplier total price must not exceed request budget",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "supplier",
        "pipeline_stage": "comply",
        "eval_config": {
            "left_field": "budget_amount",
            "operator": ">=",
            "right_field": "total_price",
            "right_constant": None,
            "condition": {
                "field": "budget_amount", "operator": "!=", "value": None,
                "and": {"field": "total_price", "operator": "!=", "value": None},
            },
        },
        "action_on_fail": "info",
        "severity": "high",
        "is_blocking": False,
        "is_skippable": True,
        "fail_message_template": "Budget {currency} {budget_amount} is below supplier total {currency} {total_price}",
        "priority": 10,
    },
    {
        "rule_id": "HR-002",
        "rule_name": "Delivery deadline feasibility",
        "description": "Supplier expedited lead time must fit within delivery window",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "supplier",
        "pipeline_stage": "comply",
        "eval_config": {
            "left_field": "days_until_required",
            "operator": ">=",
            "right_field": "expedited_lead_time_days",
            "right_constant": None,
            "condition": {
                "field": "days_until_required", "operator": "!=", "value": None,
                "and": {"field": "expedited_lead_time_days", "operator": "!=", "value": None},
            },
        },
        "action_on_fail": "info",
        "severity": "high",
        "is_blocking": False,
        "is_skippable": True,
        "fail_message_template": "Supplier needs {expedited_lead_time_days} days but only {days_until_required} available",
        "priority": 20,
    },
    {
        "rule_id": "HR-003",
        "rule_name": "Supplier monthly capacity",
        "description": "Requested quantity must not exceed supplier monthly capacity",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "supplier",
        "pipeline_stage": "comply",
        "eval_config": {
            "left_field": "capacity_per_month",
            "operator": ">=",
            "right_field": "quantity",
            "right_constant": None,
            "condition": {
                "field": "quantity", "operator": "!=", "value": None,
                "and": {"field": "capacity_per_month", "operator": "!=", "value": None},
            },
        },
        "action_on_fail": "exclude",
        "severity": "critical",
        "is_blocking": False,
        "is_skippable": True,
        "fail_message_template": "Quantity {quantity} exceeds monthly capacity {capacity_per_month}",
        "priority": 30,
    },
    {
        "rule_id": "HR-004",
        "rule_name": "Minimum order quantity",
        "description": "Requested quantity must meet supplier MOQ",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "supplier",
        "pipeline_stage": "comply",
        "eval_config": {
            "left_field": "quantity",
            "operator": ">=",
            "right_field": "moq",
            "right_constant": None,
            "condition": {
                "field": "quantity", "operator": "!=", "value": None,
                "and": {"field": "moq", "operator": "!=", "value": None},
            },
        },
        "action_on_fail": "info",
        "severity": "medium",
        "is_blocking": False,
        "is_skippable": True,
        "fail_message_template": "Quantity {quantity} is below minimum order quantity {moq}",
        "priority": 35,
    },
    {
        "rule_id": "PC-008",
        "rule_name": "Data residency constraint",
        "description": "Supplier must support data residency when the request requires it",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "supplier",
        "pipeline_stage": "comply",
        "eval_config": {
            "left_field": "data_residency_supported",
            "operator": "==",
            "right_field": None,
            "right_constant": True,
            "condition": {"field": "data_residency_constraint", "operator": "==", "value": True},
        },
        "action_on_fail": "exclude",
        "severity": "critical",
        "is_blocking": False,
        "fail_message_template": "Supplier does not support data residency in {country}",
        "priority": 40,
    },
    {
        "rule_id": "HR-RISK",
        "rule_name": "Risk score threshold",
        "description": "Non-preferred suppliers with high risk score are excluded",
        "rule_category": "hard_rule",
        "eval_type": "threshold",
        "scope": "supplier",
        "pipeline_stage": "comply",
        "eval_config": {
            "field": "risk_score",
            "min": None,
            "max": 70,
            "condition": {"field": "preferred_supplier", "operator": "==", "value": False},
        },
        "action_on_fail": "exclude",
        "severity": "high",
        "is_blocking": False,
        "fail_message_template": "Non-preferred supplier risk_score={risk_score} exceeds threshold 70",
        "priority": 50,
    },
    {
        "rule_id": "PC-004",
        "rule_name": "Restricted supplier check",
        "description": "Supplier must not be restricted for the given category and country",
        "rule_category": "hard_rule",
        "eval_type": "compare",
        "scope": "supplier",
        "pipeline_stage": "comply",
        "eval_config": {
            "left_field": "is_restricted",
            "operator": "==",
            "right_field": None,
            "right_constant": False,
            "condition": None,
        },
        "action_on_fail": "exclude",
        "severity": "critical",
        "is_blocking": False,
        "fail_message_template": "Supplier {supplier_name} is restricted: {restriction_reason}",
        "priority": 60,
    },

    # ── Escalate stage ──────────────────────────────────────────────
    {
        "rule_id": "ER-001",
        "rule_name": "Missing required info escalation",
        "description": "Escalate when budget or quantity is null (missing required information)",
        "rule_category": "escalation",
        "eval_type": "required",
        "scope": "request",
        "pipeline_stage": "escalate",
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
        "fail_message_template": "Missing required request information: {field_name}",
        "priority": 10,
    },
    {
        "rule_id": "ER-002",
        "rule_name": "Preferred supplier restricted",
        "description": "Escalate when the requester's preferred supplier is restricted",
        "rule_category": "escalation",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "escalate",
        "eval_config": {
            "left_field": "preferred_is_restricted",
            "operator": "==",
            "right_field": None,
            "right_constant": False,
            "condition": {"field": "preferred_supplier_mentioned", "operator": "!=", "value": None},
        },
        "action_on_fail": "escalate",
        "severity": "critical",
        "is_blocking": True,
        "escalation_target": "Procurement Manager",
        "fail_message_template": "Preferred supplier {preferred_supplier_mentioned} is restricted",
        "priority": 20,
    },
    {
        "rule_id": "ER-003",
        "rule_name": "Contract value exceeds strategic tier",
        "description": "Escalate when contract value triggers CPO/Head of Strategic Sourcing",
        "rule_category": "escalation",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "escalate",
        "eval_config": {
            "left_field": "approval_tier_requires_strategic",
            "operator": "==",
            "right_field": None,
            "right_constant": False,
            "condition": None,
        },
        "action_on_fail": "escalate",
        "severity": "high",
        "is_blocking": False,
        "escalation_target": "Head of Strategic Sourcing",
        "fail_message_template": "Contract value exceeds strategic sourcing tier",
        "priority": 30,
    },
    {
        "rule_id": "ER-004",
        "rule_name": "No compliant supplier found",
        "description": "Escalate when no supplier remains after compliance checks",
        "rule_category": "escalation",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "escalate",
        "eval_config": {
            "left_field": "compliant_supplier_count",
            "operator": ">",
            "right_field": None,
            "right_constant": 0,
            "condition": None,
        },
        "action_on_fail": "escalate",
        "severity": "critical",
        "is_blocking": True,
        "escalation_target": "Head of Category",
        "fail_message_template": "No compliant supplier found after compliance checks",
        "priority": 40,
    },
    {
        "rule_id": "ER-005",
        "rule_name": "Data residency unsatisfiable",
        "description": "Escalate when no compliant supplier supports data residency",
        "rule_category": "escalation",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "escalate",
        "eval_config": {
            "left_field": "has_residency_supplier",
            "operator": "==",
            "right_field": None,
            "right_constant": True,
            "condition": {"field": "data_residency_constraint", "operator": "==", "value": True},
        },
        "action_on_fail": "escalate",
        "severity": "critical",
        "is_blocking": True,
        "escalation_target": "Security/Compliance",
        "fail_message_template": "No compliant supplier supports data residency in {country}",
        "priority": 50,
    },
    {
        "rule_id": "ER-006",
        "rule_name": "Single supplier capacity risk",
        "description": "Escalate when only one compliant supplier can meet the requested quantity",
        "rule_category": "escalation",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "escalate",
        "eval_config": {
            "left_field": "single_supplier_capacity_risk",
            "operator": "==",
            "right_field": None,
            "right_constant": False,
            "condition": {
                "field": "quantity", "operator": "!=", "value": None,
            },
        },
        "action_on_fail": "escalate",
        "severity": "high",
        "is_blocking": False,
        "escalation_target": "Sourcing Excellence Lead",
        "fail_message_template": "Only one supplier can meet the requested quantity of {quantity}",
        "priority": 55,
    },
    {
        "rule_id": "ER-007",
        "rule_name": "Brand safety concern",
        "description": "Escalate influencer/marketing campaigns for brand-safety review",
        "rule_category": "escalation",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "escalate",
        "eval_config": {
            "left_field": "category_l2",
            "operator": "!=",
            "right_field": None,
            "right_constant": "Influencer Campaign Management",
            "condition": None,
        },
        "action_on_fail": "escalate",
        "severity": "high",
        "is_blocking": False,
        "escalation_target": "Marketing Governance Lead",
        "fail_message_template": "Influencer campaign requires brand-safety review before final award",
        "priority": 60,
    },
    {
        "rule_id": "ER-008",
        "rule_name": "Supplier not registered/sanctioned",
        "description": "Escalate when supplier is not registered/sanction-screened in delivery country",
        "rule_category": "escalation",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "escalate",
        "eval_config": {
            "left_field": "has_unregistered_supplier",
            "operator": "==",
            "right_field": None,
            "right_constant": False,
            "condition": {"field": "currency", "operator": "==", "value": "USD"},
        },
        "action_on_fail": "escalate",
        "severity": "high",
        "is_blocking": False,
        "escalation_target": "Regional Compliance Lead",
        "fail_message_template": "Supplier not registered or sanctioned-screened in delivery country",
        "priority": 70,
    },
    {
        "rule_id": "ER-009",
        "rule_name": "Contradictory request content",
        "description": "Flag when LLM detects genuine contradictions between text and structured fields",
        "rule_category": "escalation",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "escalate",
        "eval_config": {
            "left_field": "has_contradictions",
            "operator": "==",
            "right_field": None,
            "right_constant": False,
            "condition": None,
        },
        "action_on_fail": "escalate",
        "severity": "medium",
        "is_blocking": False,
        "escalation_target": "Procurement Manager",
        "fail_message_template": "Request contains contradictions between text and structured fields",
        "priority": 80,
    },
    {
        "rule_id": "ER-010",
        "rule_name": "Lead time infeasible escalation",
        "description": "Flag when no supplier can meet the delivery deadline",
        "rule_category": "escalation",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "escalate",
        "eval_config": {
            "left_field": "has_lead_time_issue",
            "operator": "==",
            "right_field": None,
            "right_constant": False,
            "condition": None,
        },
        "action_on_fail": "escalate",
        "severity": "high",
        "is_blocking": False,
        "escalation_target": "Head of Category",
        "fail_message_template": "Lead time infeasible: no supplier can meet the delivery deadline",
        "priority": 85,
    },

    # ── Policy stage ────────────────────────────────────────────────
    {
        "rule_id": "PC-001",
        "rule_name": "Approval tier determination",
        "description": "Document which approval tier applies based on budget/currency",
        "rule_category": "policy_check",
        "eval_type": "threshold",
        "scope": "request",
        "pipeline_stage": "policy",
        "eval_config": {
            "field": "budget_amount",
            "min": 0,
            "max": None,
            "condition": {"field": "budget_amount", "operator": "!=", "value": None},
        },
        "action_on_fail": "info",
        "severity": "medium",
        "is_blocking": False,
        "fail_message_template": "Approval tier applies for {currency} {budget_amount}",
        "priority": 10,
    },
    {
        "rule_id": "PC-002",
        "rule_name": "Quote count requirement",
        "description": "Document the number of quotes required for this tier",
        "rule_category": "policy_check",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "policy",
        "eval_config": {
            "left_field": "compliant_supplier_count",
            "operator": ">=",
            "right_field": "quotes_required",
            "right_constant": None,
            "condition": {"field": "quotes_required", "operator": "!=", "value": None},
        },
        "action_on_fail": "warn",
        "severity": "high",
        "is_blocking": False,
        "fail_message_template": "Only {compliant_supplier_count} suppliers available but {quotes_required} quotes required",
        "priority": 20,
    },
    {
        "rule_id": "PC-003",
        "rule_name": "Preferred supplier check",
        "description": "Document whether the preferred supplier is in the compliant set",
        "rule_category": "policy_check",
        "eval_type": "compare",
        "scope": "request",
        "pipeline_stage": "policy",
        "eval_config": {
            "left_field": "preferred_in_compliant",
            "operator": "==",
            "right_field": None,
            "right_constant": True,
            "condition": {"field": "preferred_supplier_mentioned", "operator": "!=", "value": None},
        },
        "action_on_fail": "info",
        "severity": "medium",
        "is_blocking": False,
        "fail_message_template": "Preferred supplier {preferred_supplier_mentioned} is not in the compliant set",
        "priority": 30,
    },
    {
        "rule_id": "PC-007",
        "rule_name": "Category sourcing rules",
        "description": "Document applicable category-specific sourcing rules",
        "rule_category": "policy_check",
        "eval_type": "set_membership",
        "scope": "request",
        "pipeline_stage": "policy",
        "eval_config": {
            "field": "category_l2",
            "set_field": "category_rule_categories",
            "expected_in_set": True,
        },
        "action_on_fail": "info",
        "severity": "medium",
        "is_blocking": False,
        "fail_message_template": "Category rule applies for {category_l2}",
        "priority": 40,
    },
    {
        "rule_id": "PC-009",
        "rule_name": "Geography/delivery compliance",
        "description": "Document applicable geography rules for delivery countries",
        "rule_category": "policy_check",
        "eval_type": "set_membership",
        "scope": "request",
        "pipeline_stage": "policy",
        "eval_config": {
            "field": "country",
            "set_field": "geography_rule_countries",
            "expected_in_set": True,
        },
        "action_on_fail": "info",
        "severity": "medium",
        "is_blocking": False,
        "fail_message_template": "Geography rule applies for delivery to {country}",
        "priority": 50,
    },
]


def seed_rules(cursor):
    for rule in SEED_RULES:
        config_json = json.dumps(rule["eval_config"])
        cursor.execute("""
            INSERT INTO dynamic_rules
            (rule_id, rule_name, description, rule_category, eval_type, scope,
             pipeline_stage, eval_config, action_on_fail, severity, is_blocking,
             escalation_target, fail_message_template, is_active, is_skippable,
             priority, version, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
            ON DUPLICATE KEY UPDATE
                rule_name = VALUES(rule_name),
                description = VALUES(description),
                rule_category = VALUES(rule_category),
                eval_type = VALUES(eval_type),
                scope = VALUES(scope),
                pipeline_stage = VALUES(pipeline_stage),
                eval_config = VALUES(eval_config),
                action_on_fail = VALUES(action_on_fail),
                severity = VALUES(severity),
                is_blocking = VALUES(is_blocking),
                escalation_target = VALUES(escalation_target),
                fail_message_template = VALUES(fail_message_template),
                is_skippable = VALUES(is_skippable),
                priority = VALUES(priority)
        """, (
            rule["rule_id"],
            rule["rule_name"],
            rule.get("description"),
            rule["rule_category"],
            rule["eval_type"],
            rule["scope"],
            rule["pipeline_stage"],
            config_json,
            rule["action_on_fail"],
            rule["severity"],
            rule.get("is_blocking", False),
            rule.get("escalation_target"),
            rule.get("fail_message_template"),
            True,
            rule.get("is_skippable", False),
            rule.get("priority", 100),
            "system_migration",
        ))


def seed_versions(cursor):
    cursor.execute("SELECT rule_id, version FROM dynamic_rules")
    rules = {row[0]: row[1] for row in cursor.fetchall()}

    for rule_id, current_version in rules.items():
        cursor.execute(
            "SELECT MAX(version) FROM dynamic_rule_versions WHERE rule_id = %s",
            (rule_id,),
        )
        max_ver_row = cursor.fetchone()
        max_ver = max_ver_row[0] if max_ver_row and max_ver_row[0] else 0

        if max_ver >= current_version:
            continue

        cursor.execute(
            "SELECT rule_id, rule_name, description, rule_category, eval_type, scope, "
            "pipeline_stage, eval_config, action_on_fail, severity, is_blocking, "
            "escalation_target, fail_message_template, is_active, is_skippable, priority "
            "FROM dynamic_rules WHERE rule_id = %s",
            (rule_id,),
        )
        row = cursor.fetchone()
        if not row:
            continue

        snapshot = {
            "rule_id": row[0], "rule_name": row[1], "description": row[2],
            "rule_category": row[3], "eval_type": row[4], "scope": row[5],
            "pipeline_stage": row[6], "eval_config": json.loads(row[7]) if isinstance(row[7], str) else row[7],
            "action_on_fail": row[8], "severity": row[9], "is_blocking": bool(row[10]),
            "escalation_target": row[11], "fail_message_template": row[12],
            "is_active": bool(row[13]), "is_skippable": bool(row[14]), "priority": row[15],
        }

        new_version = max_ver + 1
        if max_ver > 0:
            cursor.execute(
                "UPDATE dynamic_rule_versions SET valid_to = NOW() "
                "WHERE rule_id = %s AND valid_to IS NULL",
                (rule_id,),
            )

        cursor.execute(
            "INSERT INTO dynamic_rule_versions (rule_id, version, snapshot, valid_from, changed_by, change_reason) "
            "VALUES (%s, %s, %s, NOW(), %s, %s)",
            (rule_id, new_version, json.dumps(snapshot), "system_migration",
             "Initial seed" if new_version == 1 else "Updated by migration"),
        )

        cursor.execute(
            "UPDATE dynamic_rules SET version = %s WHERE rule_id = %s",
            (new_version, rule_id),
        )


def run():
    conn = get_connection()
    cursor = conn.cursor()

    print("Creating dynamic rule tables...")
    create_tables(cursor)
    conn.commit()

    print("Seeding rules...")
    seed_rules(cursor)
    conn.commit()

    print("Seeding version 1 snapshots...")
    seed_versions(cursor)
    conn.commit()

    cursor.execute("SELECT COUNT(*) FROM dynamic_rules")
    rule_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM dynamic_rule_versions")
    version_count = cursor.fetchone()[0]
    print(f"Done. {rule_count} rules, {version_count} versions.")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    try:
        run()
    except mysql.connector.Error as e:
        print(f"\nDatabase error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
