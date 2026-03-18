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
from pathlib import Path

import mysql.connector
from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# ---------------------------------------------------------------------------
# Schema definitions
# ---------------------------------------------------------------------------

DROP_TABLES = [
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
            r["created_at"],
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
    print("Creating 22 tables...")
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
