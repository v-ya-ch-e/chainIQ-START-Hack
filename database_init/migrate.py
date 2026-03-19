"""
Database migration script for ChainIQ procurement data.

Reads all 6 data files from ../data/, normalizes them into a proper relational
schema (22 tables), and loads them into an AWS RDS MySQL instance.

Usage:
    source .venv/bin/activate
    python migrate.py
"""

import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

DROP_TABLES = [
    "audit_logs",
    "pipeline_log_entries",
    "pipeline_runs",
    "rule_versions",
    "rule_definitions",
    "escalation_rule_currencies",
    "escalation_rules",
    "geography_rule_applies_to_categories",
    "geography_rule_countries",
    "geography_rules",
    "category_rules",
    "restricted_supplier_scopes",
    "restricted_suppliers_policy",
    "preferred_supplier_region_scopes",
    "preferred_suppliers_policy",
    "approval_threshold_deviation_approvers",
    "approval_threshold_managers",
    "approval_thresholds",
    "request_scenario_tags",
    "request_delivery_countries",
    "historical_awards",
    "requests",
    "pricing_tiers",
    "supplier_service_regions",
    "supplier_categories",
    "suppliers",
    "categories",
]

CREATE_TABLES = [
    # -- Reference data --
    """
    CREATE TABLE categories (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        category_l1     VARCHAR(50)  NOT NULL,
        category_l2     VARCHAR(80)  NOT NULL,
        category_description VARCHAR(255) NOT NULL,
        typical_unit    VARCHAR(30)  NOT NULL,
        pricing_model   VARCHAR(30)  NOT NULL,
        UNIQUE KEY uq_category (category_l1, category_l2)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE suppliers (
        supplier_id     VARCHAR(20)  PRIMARY KEY,
        supplier_name   VARCHAR(120) NOT NULL,
        country_hq      VARCHAR(5)   NOT NULL,
        currency        VARCHAR(5)   NOT NULL,
        contract_status VARCHAR(20)  NOT NULL,
        capacity_per_month INT       NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE supplier_categories (
        id                      INT AUTO_INCREMENT PRIMARY KEY,
        supplier_id             VARCHAR(20)  NOT NULL,
        category_id             INT          NOT NULL,
        pricing_model           VARCHAR(30)  NOT NULL,
        quality_score           INT          NOT NULL,
        risk_score              INT          NOT NULL,
        esg_score               INT          NOT NULL,
        preferred_supplier      BOOLEAN      NOT NULL,
        is_restricted           BOOLEAN      NOT NULL,
        restriction_reason      TEXT,
        data_residency_supported BOOLEAN     NOT NULL,
        notes                   TEXT,
        UNIQUE KEY uq_supplier_cat (supplier_id, category_id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
        FOREIGN KEY (category_id) REFERENCES categories(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE supplier_service_regions (
        supplier_id  VARCHAR(20) NOT NULL,
        country_code VARCHAR(5)  NOT NULL,
        PRIMARY KEY (supplier_id, country_code),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE pricing_tiers (
        pricing_id              VARCHAR(20)  PRIMARY KEY,
        supplier_id             VARCHAR(20)  NOT NULL,
        category_id             INT          NOT NULL,
        region                  VARCHAR(20)  NOT NULL,
        currency                VARCHAR(5)   NOT NULL,
        pricing_model           VARCHAR(30)  NOT NULL,
        min_quantity            INT          NOT NULL,
        max_quantity            INT          NOT NULL,
        unit_price              DECIMAL(12,4) NOT NULL,
        moq                     INT          NOT NULL,
        standard_lead_time_days INT          NOT NULL,
        expedited_lead_time_days INT         NOT NULL,
        expedited_unit_price    DECIMAL(12,4) NOT NULL,
        valid_from              DATE         NOT NULL,
        valid_to                DATE         NOT NULL,
        notes                   TEXT,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
        FOREIGN KEY (category_id) REFERENCES categories(id),
        INDEX idx_pricing_lookup (supplier_id, category_id, region)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Requests --
    """
    CREATE TABLE requests (
        request_id                  VARCHAR(20)  PRIMARY KEY,
        created_at                  DATETIME     NOT NULL,
        request_channel             VARCHAR(20)  NOT NULL,
        request_language            VARCHAR(5)   NOT NULL,
        business_unit               VARCHAR(80)  NOT NULL,
        country                     VARCHAR(5)   NOT NULL,
        site                        VARCHAR(80)  NOT NULL,
        requester_id                VARCHAR(20)  NOT NULL,
        requester_role              VARCHAR(80),
        submitted_for_id            VARCHAR(20)  NOT NULL,
        category_id                 INT          NOT NULL,
        title                       VARCHAR(255) NOT NULL,
        request_text                TEXT         NOT NULL,
        currency                    VARCHAR(5)   NOT NULL,
        budget_amount               DECIMAL(14,2),
        quantity                    DECIMAL(14,2),
        unit_of_measure             VARCHAR(30)  NOT NULL,
        required_by_date            DATE         NOT NULL,
        preferred_supplier_mentioned VARCHAR(120),
        incumbent_supplier          VARCHAR(120),
        contract_type_requested     VARCHAR(40)  NOT NULL,
        data_residency_constraint   BOOLEAN      NOT NULL,
        esg_requirement             BOOLEAN      NOT NULL,
        status                      VARCHAR(20)  NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories(id),
        INDEX idx_req_category (category_id),
        INDEX idx_req_country (country)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE request_delivery_countries (
        id           INT AUTO_INCREMENT PRIMARY KEY,
        request_id   VARCHAR(20) NOT NULL,
        country_code VARCHAR(5)  NOT NULL,
        UNIQUE KEY uq_req_country (request_id, country_code),
        FOREIGN KEY (request_id) REFERENCES requests(request_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE request_scenario_tags (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        request_id VARCHAR(20)  NOT NULL,
        tag        VARCHAR(30)  NOT NULL,
        UNIQUE KEY uq_req_tag (request_id, tag),
        FOREIGN KEY (request_id) REFERENCES requests(request_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Historical --
    """
    CREATE TABLE historical_awards (
        award_id                VARCHAR(20)   PRIMARY KEY,
        request_id              VARCHAR(20)   NOT NULL,
        award_date              DATE          NOT NULL,
        category_id             INT           NOT NULL,
        country                 VARCHAR(5)    NOT NULL,
        business_unit           VARCHAR(80)   NOT NULL,
        supplier_id             VARCHAR(20)   NOT NULL,
        supplier_name           VARCHAR(120)  NOT NULL,
        total_value             DECIMAL(14,2) NOT NULL,
        currency                VARCHAR(5)    NOT NULL,
        quantity                DECIMAL(14,2) NOT NULL,
        required_by_date        DATE          NOT NULL,
        awarded                 BOOLEAN       NOT NULL,
        award_rank              INT           NOT NULL,
        decision_rationale      TEXT          NOT NULL,
        policy_compliant        BOOLEAN       NOT NULL,
        preferred_supplier_used BOOLEAN       NOT NULL,
        escalation_required     BOOLEAN       NOT NULL,
        escalated_to            VARCHAR(80),
        savings_pct             DECIMAL(6,2)  NOT NULL,
        lead_time_days          INT           NOT NULL,
        risk_score_at_award     INT           NOT NULL,
        notes                   TEXT,
        FOREIGN KEY (request_id) REFERENCES requests(request_id),
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
        FOREIGN KEY (category_id) REFERENCES categories(id),
        INDEX idx_award_request (request_id),
        INDEX idx_award_supplier (supplier_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Policies: approval thresholds --
    """
    CREATE TABLE approval_thresholds (
        threshold_id        VARCHAR(20)  PRIMARY KEY,
        currency            VARCHAR(5)   NOT NULL,
        min_amount          DECIMAL(14,2) NOT NULL,
        max_amount          DECIMAL(14,2),
        min_supplier_quotes INT          NOT NULL,
        policy_note         TEXT,
        INDEX idx_threshold_currency (currency)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE approval_threshold_managers (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        threshold_id  VARCHAR(20)  NOT NULL,
        manager_role  VARCHAR(80)  NOT NULL,
        UNIQUE KEY uq_thresh_mgr (threshold_id, manager_role),
        FOREIGN KEY (threshold_id) REFERENCES approval_thresholds(threshold_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE approval_threshold_deviation_approvers (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        threshold_id  VARCHAR(20)  NOT NULL,
        approver_role VARCHAR(80)  NOT NULL,
        UNIQUE KEY uq_thresh_dev (threshold_id, approver_role),
        FOREIGN KEY (threshold_id) REFERENCES approval_thresholds(threshold_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Policies: preferred suppliers --
    """
    CREATE TABLE preferred_suppliers_policy (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        supplier_id     VARCHAR(20)  NOT NULL,
        category_l1     VARCHAR(50)  NOT NULL,
        category_l2     VARCHAR(80)  NOT NULL,
        policy_note     TEXT,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
        INDEX idx_pref_supplier (supplier_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE preferred_supplier_region_scopes (
        id                          INT AUTO_INCREMENT PRIMARY KEY,
        preferred_suppliers_policy_id INT NOT NULL,
        region                      VARCHAR(20) NOT NULL,
        UNIQUE KEY uq_pref_region (preferred_suppliers_policy_id, region),
        FOREIGN KEY (preferred_suppliers_policy_id) REFERENCES preferred_suppliers_policy(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Policies: restricted suppliers --
    """
    CREATE TABLE restricted_suppliers_policy (
        id                  INT AUTO_INCREMENT PRIMARY KEY,
        supplier_id         VARCHAR(20)  NOT NULL,
        category_l1         VARCHAR(50)  NOT NULL,
        category_l2         VARCHAR(80)  NOT NULL,
        restriction_reason  TEXT         NOT NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id),
        INDEX idx_rest_supplier (supplier_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE restricted_supplier_scopes (
        id                          INT AUTO_INCREMENT PRIMARY KEY,
        restricted_suppliers_policy_id INT NOT NULL,
        scope_value                 VARCHAR(10) NOT NULL,
        UNIQUE KEY uq_rest_scope (restricted_suppliers_policy_id, scope_value),
        FOREIGN KEY (restricted_suppliers_policy_id) REFERENCES restricted_suppliers_policy(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Policies: category rules --
    """
    CREATE TABLE category_rules (
        rule_id      VARCHAR(20) PRIMARY KEY,
        category_id  INT         NOT NULL,
        rule_type    VARCHAR(40) NOT NULL,
        rule_text    TEXT        NOT NULL,
        FOREIGN KEY (category_id) REFERENCES categories(id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Policies: geography rules --
    """
    CREATE TABLE geography_rules (
        rule_id    VARCHAR(20)  PRIMARY KEY,
        country    VARCHAR(5),
        region     VARCHAR(20),
        rule_type  VARCHAR(40),
        rule_text  TEXT         NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE geography_rule_countries (
        id         INT AUTO_INCREMENT PRIMARY KEY,
        rule_id    VARCHAR(20) NOT NULL,
        country_code VARCHAR(5) NOT NULL,
        UNIQUE KEY uq_geo_country (rule_id, country_code),
        FOREIGN KEY (rule_id) REFERENCES geography_rules(rule_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE geography_rule_applies_to_categories (
        id          INT AUTO_INCREMENT PRIMARY KEY,
        rule_id     VARCHAR(20)  NOT NULL,
        category_l1 VARCHAR(50)  NOT NULL,
        UNIQUE KEY uq_geo_cat (rule_id, category_l1),
        FOREIGN KEY (rule_id) REFERENCES geography_rules(rule_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Policies: escalation rules --
    """
    CREATE TABLE escalation_rules (
        rule_id            VARCHAR(20)  PRIMARY KEY,
        trigger_condition  VARCHAR(120) NOT NULL,
        action             VARCHAR(120) NOT NULL,
        escalate_to        VARCHAR(80)  NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE escalation_rule_currencies (
        id        INT AUTO_INCREMENT PRIMARY KEY,
        rule_id   VARCHAR(20) NOT NULL,
        currency  VARCHAR(5)  NOT NULL,
        UNIQUE KEY uq_esc_cur (rule_id, currency),
        FOREIGN KEY (rule_id) REFERENCES escalation_rules(rule_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Rule definitions + versions (data-driven rule engine) --
    """
    CREATE TABLE rule_definitions (
        rule_id             VARCHAR(10)  PRIMARY KEY,
        rule_type           VARCHAR(30)  NOT NULL,
        rule_name           VARCHAR(100) NOT NULL,
        scope               VARCHAR(20)  NOT NULL DEFAULT 'request',
        evaluation_mode     VARCHAR(20)  NOT NULL DEFAULT 'expression',
        is_skippable        BOOLEAN      NOT NULL DEFAULT FALSE,
        source              VARCHAR(10)  NOT NULL DEFAULT 'custom',
        severity            VARCHAR(10)  NOT NULL DEFAULT 'high',
        is_blocking         BOOLEAN      NOT NULL DEFAULT TRUE,
        breaks_completeness BOOLEAN      NOT NULL DEFAULT FALSE,
        action_type         VARCHAR(30)  NOT NULL DEFAULT 'escalate',
        action_target       VARCHAR(120) NULL,
        trigger_template    TEXT         NULL,
        action_required     TEXT         NULL,
        field_ref           VARCHAR(50)  NULL,
        description         TEXT         NULL,
        active              BOOLEAN      NOT NULL DEFAULT TRUE,
        sort_order          INT          NOT NULL DEFAULT 100,
        created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_rd_rule_type (rule_type),
        INDEX idx_rd_scope (scope),
        INDEX idx_rd_active (active)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE rule_versions (
        version_id      CHAR(36)     NOT NULL,
        rule_id         VARCHAR(10)  NOT NULL,
        version_num     INT          NOT NULL,
        rule_config     JSON         NOT NULL,
        valid_from      DATETIME     NOT NULL,
        valid_to        DATETIME     NULL,
        changed_by      VARCHAR(100) NULL,
        change_reason   TEXT         NULL,
        PRIMARY KEY (version_id),
        UNIQUE KEY uq_rule_version (rule_id, version_num),
        INDEX idx_rule_valid_from (rule_id, valid_from),
        FOREIGN KEY (rule_id) REFERENCES rule_definitions(rule_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Pipeline logging --
    """
    CREATE TABLE pipeline_runs (
        id                INT AUTO_INCREMENT PRIMARY KEY,
        run_id            VARCHAR(36)  NOT NULL,
        request_id        VARCHAR(20)  NOT NULL,
        status            VARCHAR(20)  NOT NULL DEFAULT 'running',
        started_at        DATETIME     NOT NULL,
        completed_at      DATETIME,
        total_duration_ms INT,
        steps_completed   INT          NOT NULL DEFAULT 0,
        steps_failed      INT          NOT NULL DEFAULT 0,
        error_message     TEXT,
        UNIQUE KEY uq_run_id (run_id),
        FOREIGN KEY (request_id) REFERENCES requests(request_id),
        INDEX idx_run_request (request_id),
        INDEX idx_run_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    """
    CREATE TABLE pipeline_log_entries (
        id              INT AUTO_INCREMENT PRIMARY KEY,
        run_id          VARCHAR(36)  NOT NULL,
        step_name       VARCHAR(60)  NOT NULL,
        step_order      INT          NOT NULL,
        status          VARCHAR(20)  NOT NULL DEFAULT 'started',
        started_at      DATETIME     NOT NULL,
        completed_at    DATETIME,
        duration_ms     INT,
        input_summary   JSON,
        output_summary  JSON,
        error_message   TEXT,
        metadata        JSON,
        FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id),
        INDEX idx_entry_run (run_id),
        INDEX idx_entry_step (step_name)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    # -- Audit logs --
    """
    CREATE TABLE audit_logs (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        request_id    VARCHAR(20)  NOT NULL,
        run_id        VARCHAR(36),
        timestamp     DATETIME(3)  NOT NULL,
        level         VARCHAR(10)  NOT NULL DEFAULT 'info',
        category      VARCHAR(40)  NOT NULL DEFAULT 'general',
        step_name     VARCHAR(60),
        message       TEXT         NOT NULL,
        details       JSON,
        source        VARCHAR(30)  NOT NULL DEFAULT 'logical_layer',
        FOREIGN KEY (request_id) REFERENCES requests(request_id),
        INDEX idx_audit_request (request_id),
        INDEX idx_audit_run (run_id),
        INDEX idx_audit_timestamp (timestamp),
        INDEX idx_audit_category (category),
        INDEX idx_audit_level (level)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_connection():
    return mysql.connector.connect(
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
    )


def parse_bool(val: str) -> bool:
    return val.strip().lower() in ("true", "1", "yes")


def read_csv(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_json(filename: str):
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def batch_insert(cursor, sql: str, rows: list[tuple], batch_size: int = 500):
    for i in range(0, len(rows), batch_size):
        cursor.executemany(sql, rows[i : i + batch_size])


def normalize_mysql_datetime(value: str) -> str:
    """
    Normalize ISO datetime strings to MySQL DATETIME format.
    Example: 2026-04-14T10:33:00Z -> 2026-04-14 10:33:00
    """
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Data loaders — each returns normalised tuples ready for INSERT
# ---------------------------------------------------------------------------

def load_categories() -> list[tuple]:
    rows = read_csv("categories.csv")
    return [
        (r["category_l1"], r["category_l2"], r["category_description"],
         r["typical_unit"], r["pricing_model"])
        for r in rows
    ]


def build_category_lookup(cursor) -> dict[tuple[str, str], int]:
    """Return {(category_l1, category_l2): id} after categories are inserted."""
    cursor.execute("SELECT id, category_l1, category_l2 FROM categories")
    return {(row[1], row[2]): row[0] for row in cursor.fetchall()}


def load_suppliers(raw_rows: list[dict]) -> tuple[list[tuple], list[tuple], list[tuple]]:
    """
    Returns (suppliers, supplier_categories_data, service_regions).
    Deduplicates suppliers from 151 rows -> 40 unique.
    """
    seen_suppliers: dict[str, tuple] = {}
    supplier_cats: list[tuple] = []
    service_regions: list[tuple] = []
    seen_regions: set[tuple[str, str]] = set()

    for r in raw_rows:
        sid = r["supplier_id"]
        if sid not in seen_suppliers:
            seen_suppliers[sid] = (
                sid,
                r["supplier_name"],
                r["country_hq"],
                r["currency"],
                r["contract_status"],
                int(r["capacity_per_month"]),
            )

        supplier_cats.append((
            sid,
            r["category_l1"], r["category_l2"],
            r["pricing_model"],
            int(r["quality_score"]),
            int(r["risk_score"]),
            int(r["esg_score"]),
            parse_bool(r["preferred_supplier"]),
            parse_bool(r["is_restricted"]),
            r["restriction_reason"] or None,
            parse_bool(r["data_residency_supported"]),
            r["notes"] or None,
        ))

        for country in r["service_regions"].split(";"):
            country = country.strip()
            if country and (sid, country) not in seen_regions:
                seen_regions.add((sid, country))
                service_regions.append((sid, country))

    return list(seen_suppliers.values()), supplier_cats, service_regions


def load_pricing(raw_rows: list[dict]) -> list[tuple]:
    return [
        (
            r["pricing_id"], r["supplier_id"],
            r["category_l1"], r["category_l2"],
            r["region"], r["currency"], r["pricing_model"],
            int(r["min_quantity"]), int(r["max_quantity"]),
            float(r["unit_price"]), int(r["moq"]),
            int(r["standard_lead_time_days"]),
            int(r["expedited_lead_time_days"]),
            float(r["expedited_unit_price"]),
            r["valid_from"], r["valid_to"],
            r["notes"] or None,
        )
        for r in raw_rows
    ]


def load_requests(raw: list[dict]) -> tuple[list[tuple], list[tuple], list[tuple]]:
    """Returns (requests_rows, delivery_countries, scenario_tags)."""
    reqs = []
    delivery = []
    tags = []

    for r in raw:
        reqs.append((
            r["request_id"],
            normalize_mysql_datetime(r["created_at"]),
            r["request_channel"],
            r["request_language"],
            r["business_unit"],
            r["country"],
            r["site"],
            r["requester_id"],
            r.get("requester_role"),
            r["submitted_for_id"],
            r["category_l1"], r["category_l2"],
            r["title"],
            r["request_text"],
            r["currency"],
            r["budget_amount"],
            r["quantity"],
            r["unit_of_measure"],
            r["required_by_date"],
            r.get("preferred_supplier_mentioned"),
            r.get("incumbent_supplier"),
            r["contract_type_requested"],
            r["data_residency_constraint"],
            r["esg_requirement"],
            r["status"],
        ))
        for c in r.get("delivery_countries", []):
            delivery.append((r["request_id"], c))
        for t in r.get("scenario_tags", []):
            tags.append((r["request_id"], t))

    return reqs, delivery, tags


def load_historical_awards(raw_rows: list[dict]) -> list[tuple]:
    return [
        (
            r["award_id"], r["request_id"], r["award_date"],
            r["category_l1"], r["category_l2"],
            r["country"], r["business_unit"],
            r["supplier_id"], r["supplier_name"],
            float(r["total_value"]), r["currency"],
            float(r["quantity"]), r["required_by_date"],
            parse_bool(r["awarded"]), int(r["award_rank"]),
            r["decision_rationale"],
            parse_bool(r["policy_compliant"]),
            parse_bool(r["preferred_supplier_used"]),
            parse_bool(r["escalation_required"]),
            r["escalated_to"] or None,
            float(r["savings_pct"]),
            int(r["lead_time_days"]),
            int(r["risk_score_at_award"]),
            r["notes"] or None,
        )
        for r in raw_rows
    ]


def load_approval_thresholds(raw: list[dict]) -> tuple[list[tuple], list[tuple], list[tuple]]:
    """
    Normalizes EUR/CHF schema (min_amount/max_amount/min_supplier_quotes/managed_by/
    deviation_approval_required_from) and USD schema (min_value/max_value/quotes_required/
    approvers/policy_note) into a unified structure.
    """
    thresholds = []
    managers = []
    deviation_approvers = []

    for t in raw:
        tid = t["threshold_id"]

        min_amt = t.get("min_amount", t.get("min_value"))
        max_amt = t.get("max_amount", t.get("max_value"))
        quotes = t.get("min_supplier_quotes", t.get("quotes_required"))
        managed = t.get("managed_by", t.get("approvers", []))
        dev_approvers = t.get("deviation_approval_required_from", [])
        policy_note = t.get("policy_note")

        thresholds.append((
            tid, t["currency"], min_amt, max_amt, quotes, policy_note,
        ))
        for role in managed:
            managers.append((tid, role))
        for approver in dev_approvers:
            deviation_approvers.append((tid, approver))

    return thresholds, managers, deviation_approvers


def load_preferred_suppliers(raw: list[dict]) -> tuple[list[tuple], list[tuple]]:
    policies = []
    region_scopes = []

    for i, p in enumerate(raw):
        policies.append((
            p["supplier_id"], p["category_l1"], p["category_l2"],
            p.get("policy_note"),
        ))
        for region in p.get("region_scope", []):
            region_scopes.append((i, region))

    return policies, region_scopes


def load_restricted_suppliers(raw: list[dict]) -> tuple[list[tuple], list[tuple]]:
    policies = []
    scopes = []

    for i, r in enumerate(raw):
        policies.append((
            r["supplier_id"], r["category_l1"], r["category_l2"],
            r["restriction_reason"],
        ))
        for scope in r.get("restriction_scope", []):
            scopes.append((i, scope))

    return policies, scopes


def load_category_rules(raw: list[dict]) -> list[tuple]:
    return [
        (r["rule_id"], r["category_l1"], r["category_l2"],
         r["rule_type"], r["rule_text"])
        for r in raw
    ]


def load_geography_rules(raw: list[dict]) -> tuple[list[tuple], list[tuple], list[tuple]]:
    """
    Normalizes two geography_rules schemas:
      GR-001..004: country / rule_type / rule_text
      GR-005..008: region / countries / rule / applies_to
    """
    rules = []
    countries = []
    applies_to = []

    for g in raw:
        rid = g["rule_id"]
        country = g.get("country")
        region = g.get("region")
        rule_type = g.get("rule_type")
        rule_text = g.get("rule_text", g.get("rule", ""))

        rules.append((rid, country, region, rule_type, rule_text))

        for c in g.get("countries", []):
            countries.append((rid, c))
        for cat in g.get("applies_to", []):
            applies_to.append((rid, cat))

    return rules, countries, applies_to


def load_escalation_rules(raw: list[dict]) -> tuple[list[tuple], list[tuple]]:
    """
    Normalizes escalation_rules: ER-001..007 use escalate_to,
    ER-008 uses escalation_target.
    """
    rules = []
    currencies = []

    for e in raw:
        rid = e["rule_id"]
        target = e.get("escalate_to", e.get("escalation_target"))
        rules.append((rid, e["trigger"], e["action"], target))
        for cur in e.get("applies_to_currencies", []):
            currencies.append((rid, cur))

    return rules, currencies


def load_rule_definitions() -> list[tuple]:
    """
    Seed data for rule_definitions table.
    Includes V6 original rules (HR/PC/ER) plus refactoring rules (VR/CR/PE).
    Columns: rule_id, rule_type, rule_name, scope, evaluation_mode, is_skippable, source,
    severity, is_blocking, breaks_completeness, action_type, action_target,
    trigger_template, action_required, field_ref, description, active, sort_order
    """
    return [
        # --- V6 hard rules (preserved) ---
        ("HR-001", "hard_rule", "Budget ceiling check", "request", "expression", 1, "given", "critical", 1, 0, "validation_issue", None, "Budget of {currency} {budget_amount} cannot cover {quantity} units. Minimum: {currency} {min_supplier_total}.", "Requester must increase budget or reduce quantity.", "budget_amount", "Budget ceiling check", 1, 1),
        ("HR-002", "hard_rule", "Delivery deadline feasibility", "request", "expression", 1, "given", "high", 1, 0, "validation_issue", None, "All suppliers expedited lead times exceed the {days_until_required}-day window.", "Requester must confirm delivery date constraint.", "required_by_date", "Delivery deadline feasibility", 1, 2),
        ("HR-003", "hard_rule", "Supplier monthly capacity", "supplier", "expression", 1, "given", "high", 1, 0, "exclude_supplier", None, "Quantity {req_quantity} exceeds monthly capacity {sup_capacity_per_month}.", None, None, "Supplier monthly capacity check", 1, 3),
        ("HR-004", "hard_rule", "Minimum order quantity", "supplier", "expression", 1, "given", "high", 1, 0, "exclude_supplier", None, "Quantity below MOQ.", None, None, "Minimum order quantity", 1, 4),
        ("HR-005", "hard_rule", "Pricing tier validity window", "supplier", "expression", 1, "given", "medium", 0, 0, "informational", None, "Pricing tier outside validity window.", None, None, "Pricing tier validity window", 1, 5),
        ("HR-006", "hard_rule", "Quantity/text discrepancy", "request", "expression", 1, "given", "high", 0, 0, "validation_issue", None, "Quantity field does not match quantity in request text.", None, "quantity", "Quantity/text discrepancy", 1, 6),
        ("HR-007", "hard_rule", "Currency consistency", "supplier", "expression", 1, "custom", "high", 1, 0, "exclude_supplier", None, "Currency mismatch between request and supplier.", None, "currency", "Currency consistency", 1, 7),
        # --- V6 policy rules (preserved) ---
        ("PC-001", "policy", "Approval tier determination", "request", "expression", 0, "given", "medium", 0, 0, "informational", None, "Approval tier determined.", None, None, "Approval tier determination", 1, 8),
        ("PC-002", "policy", "Quote count requirement", "request", "expression", 0, "given", "high", 1, 0, "escalate", None, "Insufficient quotes for value tier.", None, None, "Quote count requirement", 1, 9),
        ("PC-003", "policy", "Preferred supplier check", "request", "expression", 0, "given", "medium", 0, 0, "informational", None, "Preferred supplier evaluation.", None, None, "Preferred supplier check", 1, 10),
        ("PC-004", "policy", "Restricted supplier global", "supplier", "expression", 0, "given", "critical", 1, 0, "exclude_supplier", None, "Supplier is globally restricted.", None, None, "Restricted supplier global", 1, 11),
        ("PC-005", "policy", "Restricted supplier country-scoped", "supplier", "expression", 0, "given", "critical", 1, 0, "exclude_supplier", None, "Supplier restricted in delivery country.", None, None, "Restricted supplier country-scoped", 1, 12),
        ("PC-006", "policy", "Restricted supplier value-conditional", "supplier", "expression", 0, "given", "high", 1, 0, "exclude_supplier", None, "Supplier restricted above value threshold.", None, None, "Restricted supplier value-conditional", 1, 13),
        ("PC-007", "policy", "Category sourcing rules", "request", "expression", 0, "given", "medium", 0, 0, "informational", None, "Category-specific sourcing rules applied.", None, None, "Category sourcing rules", 1, 14),
        ("PC-008", "policy", "Data residency constraint", "supplier", "expression", 0, "given", "critical", 1, 0, "exclude_supplier", None, "Data residency constraint not satisfied.", None, None, "Data residency constraint", 1, 15),
        ("PC-009", "policy", "Geography/delivery compliance", "supplier", "expression", 0, "given", "high", 1, 0, "exclude_supplier", None, "Supplier does not cover delivery countries.", None, None, "Geography/delivery compliance", 1, 16),
        ("PC-010", "policy", "ESG requirement coverage", "supplier", "expression", 0, "given", "medium", 0, 0, "informational", None, "ESG requirement check.", None, None, "ESG requirement coverage", 1, 17),
        ("PC-011", "policy", "Supplier registration/sanction", "supplier", "expression", 0, "given", "critical", 1, 0, "exclude_supplier", None, "Supplier not registered or sanctioned.", None, None, "Supplier registration/sanction", 1, 18),
        ("PC-012", "policy", "Preferred supplier category mismatch", "request", "expression", 0, "custom", "high", 0, 0, "informational", None, "Preferred supplier category mismatch.", None, None, "Preferred supplier category mismatch", 1, 19),
        ("PC-013", "policy", "Preferred supplier geo mismatch", "request", "expression", 0, "custom", "high", 0, 0, "informational", None, "Preferred supplier geo mismatch.", None, None, "Preferred supplier geo mismatch", 1, 20),
        # --- Escalation rules (V6 ER-001..ER-010 + ER-AT) ---
        ("ER-001", "escalation", "Missing required info", "request", "expression", 0, "given", "critical", 1, 0, "escalate", "Requester Clarification", "Missing required request information (budget, quantity, or category).", None, None, "Missing required request information.", 1, 100),
        ("ER-002", "escalation", "Preferred supplier restricted", "request", "expression", 0, "given", "critical", 1, 0, "escalate", "Procurement Manager", "Preferred supplier is restricted for this request context.", None, None, "Preferred supplier is restricted.", 1, 101),
        ("ER-003", "escalation", "Contract value exceeds tier", "request", "expression", 0, "given", "medium", 0, 0, "escalate", "Head of Strategic Sourcing", "Contract value falls into strategic sourcing approval tier.", None, None, "Strategic sourcing tier.", 1, 102),
        ("ER-004", "escalation", "No compliant supplier found", "request", "expression", 0, "given", "critical", 1, 0, "escalate", "Head of Category", "No compliant supplier with valid pricing found.", None, None, "No compliant supplier found.", 1, 103),
        ("ER-005", "escalation", "Data residency unsatisfiable", "request", "expression", 0, "given", "critical", 1, 0, "escalate", "Security and Compliance Review", "Data residency requirement cannot be satisfied.", None, None, "Data residency unsatisfiable.", 1, 104),
        ("ER-006", "escalation", "Quantity exceeds capacity", "request", "expression", 0, "given", "high", 1, 0, "escalate", "Sourcing Excellence Lead", "Only one supplier can satisfy quantity/capacity constraints.", None, None, "Quantity exceeds capacity.", 1, 105),
        ("ER-007", "escalation", "Brand safety concern", "request", "expression", 0, "given", "high", 1, 0, "escalate", "Marketing Governance Lead", "Brand-safety review required for influencer campaigns.", None, None, "Brand safety concern.", 1, 106),
        ("ER-008", "escalation", "Supplier not registered/sanctioned", "request", "expression", 0, "given", "critical", 1, 0, "escalate", "Regional Compliance Lead", "Preferred supplier not registered for delivery countries in USD request.", None, None, "Supplier not registered.", 1, 107),
        ("ER-009", "escalation", "Contradictory request content", "request", "llm", 0, "custom", "high", 0, 0, "escalate", "Requester Clarification", "(overridden by Claude)", None, None, "Contradictory request content.", 1, 108),
        ("ER-010", "escalation", "Preferred supplier mismatch", "request", "expression", 0, "custom", "high", 0, 0, "escalate", "Procurement Manager", "Preferred supplier category or geo mismatch.", None, None, "Preferred supplier mismatch.", 1, 109),
        ("ER-AT", "escalation", "AT-conflict: quotes vs single-supplier", "request", "expression", 0, "custom", "critical", 1, 0, "escalate", "dynamic", "Requester instruction conflicts with {threshold_id}: {threshold_quotes_required} quotes required.", None, None, "AT-conflict.", 1, 110),
        # --- Validation rules (VR-001..VR-010 + VR-LLM) ---
        ("VR-001", "validation", "Missing category L1", "request", "expression", 0, "custom", "critical", 1, 1, "validation_issue", None, "category_l1 is missing.", "Requester must specify L1 category.", "category_l1", "category_l1 is missing.", 1, 200),
        ("VR-002", "validation", "Missing category L2", "request", "expression", 0, "custom", "critical", 1, 1, "validation_issue", None, "category_l2 is missing.", "Requester must specify L2 category.", "category_l2", "category_l2 is missing.", 1, 201),
        ("VR-003", "validation", "Missing currency", "request", "expression", 0, "custom", "critical", 1, 1, "validation_issue", None, "currency is missing.", "Requester must specify currency.", "currency", "currency is missing.", 1, 202),
        ("VR-004", "validation", "Missing budget", "request", "expression", 0, "custom", "high", 0, 0, "validation_issue", None, "budget_amount is null. Pipeline continues with degraded capability.", "Requester should provide a budget.", "budget_amount", "budget_amount is null.", 1, 203),
        ("VR-005", "validation", "Missing quantity", "request", "expression", 0, "custom", "high", 0, 0, "validation_issue", None, "quantity is null. Pricing comparison limited to quality-only ranking.", "Requester should provide a quantity.", "quantity", "quantity is null.", 1, 204),
        ("VR-006", "validation", "Missing delivery date", "request", "expression", 0, "custom", "medium", 0, 0, "validation_issue", None, "required_by_date is not specified.", "Requester should specify a delivery date.", "required_by_date", "required_by_date not specified.", 1, 205),
        ("VR-007", "validation", "Missing delivery countries", "request", "expression", 0, "custom", "high", 0, 0, "validation_issue", None, "No delivery countries specified.", "Requester must specify at least one delivery country.", "delivery_countries", "No delivery countries.", 1, 206),
        ("VR-008", "validation", "Date in the past", "request", "expression", 0, "custom", "critical", 0, 0, "validation_issue", None, "Required by date is in the past ({days_until_required} days ago).", "Requester must provide a future delivery date.", "required_by_date", "Required by date in the past.", 1, 207),
        ("VR-009", "validation", "Budget insufficient", "request", "expression", 0, "custom", "critical", 0, 0, "validation_issue", None, "Budget of {currency} {budget_amount} cannot cover {quantity} units. Minimum: {currency} {min_supplier_total}.", "Requester must increase budget or reduce quantity.", "budget_amount", "Budget insufficient.", 1, 208),
        ("VR-010", "validation", "Lead time infeasible", "request", "expression", 0, "custom", "high", 0, 0, "validation_issue", None, "All suppliers expedited lead times exceed the {days_until_required}-day window.", "Requester must confirm delivery date constraint.", "required_by_date", "Lead time infeasible.", 1, 209),
        ("VR-LLM", "validation", "LLM contradiction detection", "request", "llm", 0, "custom", "medium", 0, 0, "validation_issue", None, "(overridden by Claude)", "Review and resolve the contradiction before proceeding.", None, "LLM contradiction detection.", 1, 210),
        # --- Supplier compliance rules (CR-001..CR-004) ---
        ("CR-001", "supplier_compliance", "Residency check", "supplier", "expression", 0, "custom", "high", 1, 0, "exclude_supplier", None, "Does not support data residency in {delivery_country}.", None, None, "Data residency not supported.", 1, 300),
        ("CR-002", "supplier_compliance", "Capacity check", "supplier", "expression", 0, "custom", "high", 1, 0, "exclude_supplier", None, "Quantity {req_quantity} exceeds monthly capacity {sup_capacity_per_month}.", None, None, "Capacity exceeded.", 1, 301),
        ("CR-003", "supplier_compliance", "Risk score check", "supplier", "expression", 0, "custom", "high", 1, 0, "exclude_supplier", None, "Risk score {sup_risk_score} exceeds threshold (30). Excluded on risk grounds.", None, None, "Risk score too high.", 1, 302),
        ("CR-004", "supplier_compliance", "Restriction check", "supplier", "expression", 0, "custom", "high", 1, 0, "exclude_supplier", None, "Restricted: {sup_restriction_reason}.", None, None, "Restricted supplier.", 1, 303),
        # --- Pipeline escalation rules (PE-001..PE-005 + PE-LLM) ---
        ("PE-001", "pipeline_escalation", "Budget shortfall", "pipeline", "expression", 0, "custom", "critical", 1, 0, "escalate", "Requester Clarification", "Budget insufficient. Budget {currency} {budget_amount}, minimum total {currency} {min_ranked_total}.", None, None, "Budget insufficient.", 1, 400),
        ("PE-002", "pipeline_escalation", "Lead time breach", "pipeline", "expression", 0, "custom", "critical", 1, 0, "escalate", "Head of Category", "Lead time infeasible: delivery in {days_until_required} days, fastest supplier needs {min_expedited_lead_time} days.", None, None, "Lead time infeasible.", 1, 401),
        ("PE-003", "pipeline_escalation", "Residency gap", "pipeline", "expression", 0, "custom", "critical", 1, 0, "escalate", "Data Protection Officer", "No compliant supplier supports data residency in {country}.", None, None, "Data residency not satisfiable.", 1, 402),
        ("PE-004", "pipeline_escalation", "No suppliers left", "pipeline", "expression", 0, "custom", "critical", 1, 0, "escalate", "Head of Category", "No supplier remains after compliance checks.", None, None, "No compliant suppliers.", 1, 403),
        ("PE-005", "pipeline_escalation", "Preferred restricted", "pipeline", "expression", 0, "custom", "critical", 1, 0, "escalate", "Procurement Manager", "Preferred supplier was excluded as restricted.", None, None, "Preferred supplier restricted.", 1, 404),
        ("PE-LLM", "pipeline_escalation", "LLM policy conflict", "pipeline", "llm", 0, "custom", "critical", 1, 0, "escalate", "Procurement Manager", "(overridden by Claude)", None, None, "LLM policy conflict detection.", 1, 405),
    ]


def load_rule_versions() -> list[tuple]:
    """
    Seed initial rule_versions (v1) for all rule_definitions.
    rule_config JSON stores condition_expr or llm_prompt plus any version-specific config.
    Columns: rule_id, version_num, rule_config_json_str, valid_from
    UUID is generated at insert time.
    """
    import uuid as _uuid
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def _cfg(condition_expr=None, llm_prompt=None, **extra):
        cfg = {}
        if condition_expr:
            cfg["condition_expr"] = condition_expr
        if llm_prompt:
            cfg["llm_prompt"] = llm_prompt
        cfg.update(extra)
        return json.dumps(cfg)

    rows = [
        # --- V6 hard rules ---
        (str(_uuid.uuid4()), "HR-001", 1, _cfg(supported_budget_types=["upper_limit","range","null"], null_action="skip_raise_ER001", range_strategy="use_max_conservative"), now),
        (str(_uuid.uuid4()), "HR-002", 1, _cfg(min_lead_time_days_standard=1, expedited_allowed=True, null_date_action="skip_raise_ER001"), now),
        (str(_uuid.uuid4()), "HR-003", 1, _cfg(condition_expr="req_quantity is not None and sup_capacity_per_month is not None and req_quantity > sup_capacity_per_month"), now),
        (str(_uuid.uuid4()), "HR-004", 1, _cfg(check="requested_quantity >= pricing.moq", source_table="pricing_tiers"), now),
        (str(_uuid.uuid4()), "HR-005", 1, _cfg(check="evaluation_date BETWEEN pricing.valid_from AND pricing.valid_to"), now),
        (str(_uuid.uuid4()), "HR-006", 1, _cfg(check="quantity_field matches quantity_in_request_text", mismatch_action="raise_ER009"), now),
        (str(_uuid.uuid4()), "HR-007", 1, _cfg(check="request.currency matches supplier.currency OR conversion_applied", allowed_currencies=["EUR","CHF","USD"]), now),
        # --- V6 policy rules ---
        (str(_uuid.uuid4()), "PC-001", 1, _cfg(tiers={"EUR":[{"tier":1,"max":25000},{"tier":2,"max":100000},{"tier":3,"max":500000},{"tier":4,"max":5000000},{"tier":5,"max":None}],"CHF":[{"tier":1,"max":27500},{"tier":2,"max":110000},{"tier":3,"max":550000},{"tier":4,"max":5500000},{"tier":5,"max":None}],"USD":[{"tier":1,"max":27000},{"tier":2,"max":108000},{"tier":3,"max":540000},{"tier":4,"max":5400000},{"tier":5,"max":None}]}), now),
        (str(_uuid.uuid4()), "PC-002", 1, _cfg(quotes_required={"tier1":1,"tier2":2,"tier3":3,"tier4":3,"tier5":3}), now),
        (str(_uuid.uuid4()), "PC-003", 1, _cfg(check="prefer preferred_supplier if policy_compliant and commercially_competitive"), now),
        (str(_uuid.uuid4()), "PC-004", 1, _cfg(condition_expr="sup_is_restricted == True", check="supplier.is_restricted = false for global restrictions"), now),
        (str(_uuid.uuid4()), "PC-005", 1, _cfg(check="restriction applies in delivery_country"), now),
        (str(_uuid.uuid4()), "PC-006", 1, _cfg(check="contract_value <= restriction_value_threshold"), now),
        (str(_uuid.uuid4()), "PC-007", 1, _cfg(check="category_rules applied: security_review, cv_review, brand_safety per category"), now),
        (str(_uuid.uuid4()), "PC-008", 1, _cfg(condition_expr="req_data_residency_constraint == True and sup_data_residency_supported == False", raise_on_fail="ER-005"), now),
        (str(_uuid.uuid4()), "PC-009", 1, _cfg(check="supplier.service_regions covers all delivery_countries"), now),
        (str(_uuid.uuid4()), "PC-010", 1, _cfg(min_esg_score=60, check="esg_requirement = false OR supplier.esg_score >= min_esg_score"), now),
        (str(_uuid.uuid4()), "PC-011", 1, _cfg(check="supplier registered and sanction-screened in each delivery_country"), now),
        (str(_uuid.uuid4()), "PC-012", 1, _cfg(check="preferred_supplier_mentioned.category matches request.category"), now),
        (str(_uuid.uuid4()), "PC-013", 1, _cfg(check="preferred_supplier_mentioned.service_regions covers request.delivery_countries"), now),
        # --- Escalation rules ---
        (str(_uuid.uuid4()), "ER-001", 1, _cfg(condition_expr="missing_required_information == True", target="Requester", event_type="NOTIFY_REQUESTER"), now),
        (str(_uuid.uuid4()), "ER-002", 1, _cfg(condition_expr="preferred_supplier_restricted == True", target="Procurement Manager", event_type="NOTIFY_PROCUREMENT"), now),
        (str(_uuid.uuid4()), "ER-003", 1, _cfg(condition_expr="strategic_tier == True", target="Head of Strategic Sourcing", event_type="REQUEST_EXCEPTION_APPROVAL"), now),
        (str(_uuid.uuid4()), "ER-004", 1, _cfg(condition_expr="not missing_required_information and not has_compliant_priceable_supplier", target="Head of Category", event_type="BLOCK_AWARD"), now),
        (str(_uuid.uuid4()), "ER-005", 1, _cfg(condition_expr="not missing_required_information and has_residency_compatible_supplier == False", target="Security/Compliance", event_type="SECURITY_REVIEW"), now),
        (str(_uuid.uuid4()), "ER-006", 1, _cfg(condition_expr="not missing_required_information and single_supplier_capacity_risk == True", target="Sourcing Excellence Lead", event_type="NOTIFY_PROCUREMENT"), now),
        (str(_uuid.uuid4()), "ER-007", 1, _cfg(condition_expr='category_label == "Marketing / Influencer Campaign Management"', target="Marketing Governance Lead", event_type="COMPLIANCE_REVIEW"), now),
        (str(_uuid.uuid4()), "ER-008", 1, _cfg(condition_expr="preferred_supplier_unregistered_usd == True", target="Regional Compliance Lead", event_type="COMPLIANCE_REVIEW"), now),
        (str(_uuid.uuid4()), "ER-009", 1, _cfg(llm_prompt="Detect contradictions between request_text and structured fields.", target="Requester", event_type="NOTIFY_REQUESTER"), now),
        (str(_uuid.uuid4()), "ER-010", 1, _cfg(condition_expr="preferred_supplier_category_mismatch == True or preferred_supplier_geo_mismatch == True", target="Procurement Manager", event_type="NOTIFY_PROCUREMENT"), now),
        (str(_uuid.uuid4()), "ER-AT", 1, _cfg(condition_expr="threshold_quotes_required >= 2 and has_single_supplier_instruction == True"), now),
        # --- Validation rules ---
        (str(_uuid.uuid4()), "VR-001", 1, _cfg(condition_expr='category_l1 is None or category_l1 == ""'), now),
        (str(_uuid.uuid4()), "VR-002", 1, _cfg(condition_expr='category_l2 is None or category_l2 == ""'), now),
        (str(_uuid.uuid4()), "VR-003", 1, _cfg(condition_expr='currency is None or currency == ""'), now),
        (str(_uuid.uuid4()), "VR-004", 1, _cfg(condition_expr="budget_amount is None"), now),
        (str(_uuid.uuid4()), "VR-005", 1, _cfg(condition_expr="quantity is None"), now),
        (str(_uuid.uuid4()), "VR-006", 1, _cfg(condition_expr='required_by_date is None or required_by_date == ""'), now),
        (str(_uuid.uuid4()), "VR-007", 1, _cfg(condition_expr="delivery_countries_count == 0"), now),
        (str(_uuid.uuid4()), "VR-008", 1, _cfg(condition_expr="days_until_required is not None and days_until_required < 0"), now),
        (str(_uuid.uuid4()), "VR-009", 1, _cfg(condition_expr="budget_amount is not None and quantity is not None and min_supplier_total is not None and budget_amount < min_supplier_total"), now),
        (str(_uuid.uuid4()), "VR-010", 1, _cfg(condition_expr="days_until_required is not None and days_until_required >= 0 and min_expedited_lead_time is not None and days_until_required < min_expedited_lead_time"), now),
        (str(_uuid.uuid4()), "VR-LLM", 1, _cfg(llm_prompt="You are a procurement validation assistant. You receive a purchase request with both free-text and structured fields. Your job is to find CONTRADICTIONS between the text and the structured data, and to extract any explicit requester instructions.\n\nRULES:\n1. Only flag two issue types: \"missing_info\" and \"contradictory\"\n2. A contradiction exists ONLY when: quantity in text differs from quantity field, budget in text differs from budget_amount field, date in text differs from required_by_date field, currency in text differs from currency field, category in text clearly doesn't match category_l1/category_l2\n3. These are NOT contradictions: preferred_supplier_mentioned vs incumbent_supplier, urgency language without a specific date, policy concerns expressed in text\n4. Be CONSERVATIVE. When in doubt, do NOT flag.\n5. The request_text may be in any language (en, fr, de, es, pt, ja). Analyze it in its original language.\n6. Extract any explicit requester instruction (e.g., \"no exception\", \"single supplier only\", \"must use X\")."), now),
        # --- Supplier compliance rules ---
        (str(_uuid.uuid4()), "CR-001", 1, _cfg(condition_expr="req_data_residency_constraint == True and sup_data_residency_supported == False"), now),
        (str(_uuid.uuid4()), "CR-002", 1, _cfg(condition_expr="req_quantity is not None and sup_capacity_per_month is not None and req_quantity > sup_capacity_per_month"), now),
        (str(_uuid.uuid4()), "CR-003", 1, _cfg(condition_expr="sup_preferred_supplier == False and sup_risk_score > 30"), now),
        (str(_uuid.uuid4()), "CR-004", 1, _cfg(condition_expr="sup_is_restricted == True"), now),
        # --- Pipeline escalation rules ---
        (str(_uuid.uuid4()), "PE-001", 1, _cfg(condition_expr="has_budget_insufficient_issue == True and min_ranked_total is not None"), now),
        (str(_uuid.uuid4()), "PE-002", 1, _cfg(condition_expr="has_lead_time_issue == True"), now),
        (str(_uuid.uuid4()), "PE-003", 1, _cfg(condition_expr="req_data_residency_constraint == True and compliant_residency_count == 0 and compliant_count > 0"), now),
        (str(_uuid.uuid4()), "PE-004", 1, _cfg(condition_expr="compliant_count == 0 and initial_supplier_count > 0"), now),
        (str(_uuid.uuid4()), "PE-005", 1, _cfg(condition_expr="preferred_supplier_excluded_restricted == True"), now),
        (str(_uuid.uuid4()), "PE-LLM", 1, _cfg(llm_prompt='The requester gave this instruction: "{requester_instruction}". Does this instruction conflict with the procurement policy that requires {threshold_quotes_required} quotes for this value tier? Only return true if there is a clear conflict.'), now),
    ]
    return rows


# ---------------------------------------------------------------------------
# Main migration
# ---------------------------------------------------------------------------

def run_migration():
    print("Connecting to database...")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SET FOREIGN_KEY_CHECKS = 0")

    # ---- Drop existing tables ----
    print("Dropping existing tables...")
    for table in DROP_TABLES:
        cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
    cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
    conn.commit()

    # ---- Create tables ----
    print("Creating 26 tables...")
    for ddl in CREATE_TABLES:
        cursor.execute(ddl)
    conn.commit()

    # ---- Load source data ----
    print("Reading source files...")
    suppliers_csv = read_csv("suppliers.csv")
    pricing_csv = read_csv("pricing.csv")
    requests_json = read_json("requests.json")
    policies_json = read_json("policies.json")
    awards_csv = read_csv("historical_awards.csv")

    # ---- 1. Categories ----
    print("  Inserting categories...")
    cat_rows = load_categories()
    batch_insert(cursor,
        "INSERT INTO categories (category_l1, category_l2, category_description, typical_unit, pricing_model) VALUES (%s,%s,%s,%s,%s)",
        cat_rows)
    conn.commit()

    cat_lookup = build_category_lookup(cursor)

    # ---- 2. Suppliers (deduplicated) ----
    print("  Inserting suppliers...")
    sup_rows, sup_cat_data, svc_regions = load_suppliers(suppliers_csv)
    batch_insert(cursor,
        "INSERT INTO suppliers (supplier_id, supplier_name, country_hq, currency, contract_status, capacity_per_month) VALUES (%s,%s,%s,%s,%s,%s)",
        sup_rows)
    conn.commit()

    # ---- 3. Supplier categories ----
    print("  Inserting supplier_categories...")
    sc_insert = []
    for sc in sup_cat_data:
        sid, c1, c2 = sc[0], sc[1], sc[2]
        cid = cat_lookup.get((c1, c2))
        if cid is None:
            print(f"    WARNING: category ({c1}, {c2}) not found for supplier {sid}, skipping")
            continue
        sc_insert.append((sid, cid) + sc[3:])
    batch_insert(cursor,
        "INSERT INTO supplier_categories (supplier_id, category_id, pricing_model, quality_score, risk_score, esg_score, preferred_supplier, is_restricted, restriction_reason, data_residency_supported, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        sc_insert)
    conn.commit()

    # ---- 4. Supplier service regions ----
    print("  Inserting supplier_service_regions...")
    batch_insert(cursor,
        "INSERT INTO supplier_service_regions (supplier_id, country_code) VALUES (%s,%s)",
        svc_regions)
    conn.commit()

    # ---- 5. Pricing tiers ----
    print("  Inserting pricing_tiers...")
    pricing_data = load_pricing(pricing_csv)
    pt_insert = []
    for p in pricing_data:
        pid, sid, c1, c2 = p[0], p[1], p[2], p[3]
        cid = cat_lookup.get((c1, c2))
        if cid is None:
            print(f"    WARNING: category ({c1}, {c2}) not found for pricing {pid}, skipping")
            continue
        pt_insert.append((pid, sid, cid) + p[4:])
    batch_insert(cursor,
        "INSERT INTO pricing_tiers (pricing_id, supplier_id, category_id, region, currency, pricing_model, min_quantity, max_quantity, unit_price, moq, standard_lead_time_days, expedited_lead_time_days, expedited_unit_price, valid_from, valid_to, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        pt_insert)
    conn.commit()

    # ---- 6. Requests ----
    print("  Inserting requests...")
    req_data, req_countries, req_tags = load_requests(requests_json)
    req_insert = []
    for r in req_data:
        c1, c2 = r[10], r[11]
        cid = cat_lookup.get((c1, c2))
        if cid is None:
            print(f"    WARNING: category ({c1}, {c2}) not found for request {r[0]}, skipping")
            continue
        req_insert.append(r[:10] + (cid,) + r[12:])
    batch_insert(cursor,
        "INSERT INTO requests (request_id, created_at, request_channel, request_language, business_unit, country, site, requester_id, requester_role, submitted_for_id, category_id, title, request_text, currency, budget_amount, quantity, unit_of_measure, required_by_date, preferred_supplier_mentioned, incumbent_supplier, contract_type_requested, data_residency_constraint, esg_requirement, status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        req_insert)
    conn.commit()

    # ---- 7. Request delivery countries ----
    print("  Inserting request_delivery_countries...")
    batch_insert(cursor,
        "INSERT INTO request_delivery_countries (request_id, country_code) VALUES (%s,%s)",
        req_countries)
    conn.commit()

    # ---- 8. Request scenario tags ----
    print("  Inserting request_scenario_tags...")
    batch_insert(cursor,
        "INSERT INTO request_scenario_tags (request_id, tag) VALUES (%s,%s)",
        req_tags)
    conn.commit()

    # ---- 9. Historical awards ----
    print("  Inserting historical_awards...")
    awards_data = load_historical_awards(awards_csv)
    awards_insert = []
    for a in awards_data:
        c1, c2 = a[3], a[4]
        cid = cat_lookup.get((c1, c2))
        if cid is None:
            print(f"    WARNING: category ({c1}, {c2}) not found for award {a[0]}, skipping")
            continue
        awards_insert.append(a[:3] + (cid,) + a[5:])
    batch_insert(cursor,
        "INSERT INTO historical_awards (award_id, request_id, award_date, category_id, country, business_unit, supplier_id, supplier_name, total_value, currency, quantity, required_by_date, awarded, award_rank, decision_rationale, policy_compliant, preferred_supplier_used, escalation_required, escalated_to, savings_pct, lead_time_days, risk_score_at_award, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        awards_insert)
    conn.commit()

    # ---- 10. Approval thresholds ----
    print("  Inserting approval_thresholds...")
    at_rows, at_mgrs, at_devs = load_approval_thresholds(policies_json["approval_thresholds"])
    batch_insert(cursor,
        "INSERT INTO approval_thresholds (threshold_id, currency, min_amount, max_amount, min_supplier_quotes, policy_note) VALUES (%s,%s,%s,%s,%s,%s)",
        at_rows)
    conn.commit()

    print("  Inserting approval_threshold_managers...")
    batch_insert(cursor,
        "INSERT INTO approval_threshold_managers (threshold_id, manager_role) VALUES (%s,%s)",
        at_mgrs)
    conn.commit()

    print("  Inserting approval_threshold_deviation_approvers...")
    batch_insert(cursor,
        "INSERT INTO approval_threshold_deviation_approvers (threshold_id, approver_role) VALUES (%s,%s)",
        at_devs)
    conn.commit()

    # ---- 11. Preferred suppliers policy ----
    print("  Inserting preferred_suppliers_policy...")
    pref_rows, pref_regions = load_preferred_suppliers(policies_json["preferred_suppliers"])
    batch_insert(cursor,
        "INSERT INTO preferred_suppliers_policy (supplier_id, category_l1, category_l2, policy_note) VALUES (%s,%s,%s,%s)",
        pref_rows)
    conn.commit()

    # Map the 0-based index to the auto-generated IDs
    cursor.execute("SELECT id FROM preferred_suppliers_policy ORDER BY id")
    pref_ids = [row[0] for row in cursor.fetchall()]
    pref_region_insert = [(pref_ids[idx], region) for idx, region in pref_regions]

    print("  Inserting preferred_supplier_region_scopes...")
    batch_insert(cursor,
        "INSERT INTO preferred_supplier_region_scopes (preferred_suppliers_policy_id, region) VALUES (%s,%s)",
        pref_region_insert)
    conn.commit()

    # ---- 12. Restricted suppliers policy ----
    print("  Inserting restricted_suppliers_policy...")
    rest_rows, rest_scopes = load_restricted_suppliers(policies_json["restricted_suppliers"])
    batch_insert(cursor,
        "INSERT INTO restricted_suppliers_policy (supplier_id, category_l1, category_l2, restriction_reason) VALUES (%s,%s,%s,%s)",
        rest_rows)
    conn.commit()

    cursor.execute("SELECT id FROM restricted_suppliers_policy ORDER BY id")
    rest_ids = [row[0] for row in cursor.fetchall()]
    rest_scope_insert = [(rest_ids[idx], scope) for idx, scope in rest_scopes]

    print("  Inserting restricted_supplier_scopes...")
    batch_insert(cursor,
        "INSERT INTO restricted_supplier_scopes (restricted_suppliers_policy_id, scope_value) VALUES (%s,%s)",
        rest_scope_insert)
    conn.commit()

    # ---- 13. Category rules ----
    print("  Inserting category_rules...")
    cr_raw = load_category_rules(policies_json["category_rules"])
    cr_insert = []
    for cr in cr_raw:
        cid = cat_lookup.get((cr[1], cr[2]))
        if cid is None:
            print(f"    WARNING: category ({cr[1]}, {cr[2]}) not found for rule {cr[0]}, skipping")
            continue
        cr_insert.append((cr[0], cid, cr[3], cr[4]))
    batch_insert(cursor,
        "INSERT INTO category_rules (rule_id, category_id, rule_type, rule_text) VALUES (%s,%s,%s,%s)",
        cr_insert)
    conn.commit()

    # ---- 14. Geography rules ----
    print("  Inserting geography_rules...")
    geo_rules, geo_countries, geo_applies = load_geography_rules(policies_json["geography_rules"])
    batch_insert(cursor,
        "INSERT INTO geography_rules (rule_id, country, region, rule_type, rule_text) VALUES (%s,%s,%s,%s,%s)",
        geo_rules)
    conn.commit()

    print("  Inserting geography_rule_countries...")
    batch_insert(cursor,
        "INSERT INTO geography_rule_countries (rule_id, country_code) VALUES (%s,%s)",
        geo_countries)
    conn.commit()

    print("  Inserting geography_rule_applies_to_categories...")
    batch_insert(cursor,
        "INSERT INTO geography_rule_applies_to_categories (rule_id, category_l1) VALUES (%s,%s)",
        geo_applies)
    conn.commit()

    # ---- 15. Escalation rules ----
    print("  Inserting escalation_rules...")
    esc_rules, esc_currencies = load_escalation_rules(policies_json["escalation_rules"])
    batch_insert(cursor,
        "INSERT INTO escalation_rules (rule_id, trigger_condition, action, escalate_to) VALUES (%s,%s,%s,%s)",
        esc_rules)
    conn.commit()

    print("  Inserting escalation_rule_currencies...")
    batch_insert(cursor,
        "INSERT INTO escalation_rule_currencies (rule_id, currency) VALUES (%s,%s)",
        esc_currencies)
    conn.commit()

    # ---- 16. Rule definitions + versions (data-driven rule engine) ----
    print("  Inserting rule_definitions...")
    rd_rows = load_rule_definitions()
    batch_insert(cursor,
        """INSERT INTO rule_definitions (
            rule_id, rule_type, rule_name, scope, evaluation_mode, is_skippable, source,
            severity, is_blocking, breaks_completeness, action_type, action_target,
            trigger_template, action_required, field_ref, description, active, sort_order
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        rd_rows)
    conn.commit()

    print("  Inserting rule_versions...")
    rv_rows = load_rule_versions()
    batch_insert(cursor,
        """INSERT INTO rule_versions (
            version_id, rule_id, version_num, rule_config, valid_from
        ) VALUES (%s,%s,%s,%s,%s)""",
        rv_rows)
    conn.commit()

    # ---- Verification ----
    print("\n=== Migration Summary ===")
    all_tables = [
        "categories", "suppliers", "supplier_categories", "supplier_service_regions",
        "pricing_tiers", "requests", "request_delivery_countries", "request_scenario_tags",
        "historical_awards",
        "approval_thresholds", "approval_threshold_managers", "approval_threshold_deviation_approvers",
        "preferred_suppliers_policy", "preferred_supplier_region_scopes",
        "restricted_suppliers_policy", "restricted_supplier_scopes",
        "category_rules",
        "geography_rules", "geography_rule_countries", "geography_rule_applies_to_categories",
        "escalation_rules", "escalation_rule_currencies",
        "rule_definitions", "rule_versions",
        "pipeline_runs", "pipeline_log_entries", "audit_logs",
    ]
    total = 0
    for table in all_tables:
        cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
        count = cursor.fetchone()[0]
        total += count
        print(f"  {table:45s} {count:>6d} rows")
    print(f"  {'TOTAL':45s} {total:>6d} rows")

    cursor.close()
    conn.close()
    print("\nMigration completed successfully.")


if __name__ == "__main__":
    try:
        run_migration()
    except mysql.connector.Error as e:
        print(f"\nDatabase error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
