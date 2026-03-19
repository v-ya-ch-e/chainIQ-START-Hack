"""
Run rule versioning migrations (rule_definitions, rule_versions, evaluation tables).
Run after migrate.py. Idempotent — uses CREATE TABLE IF NOT EXISTS.
"""

import os
import sys
from pathlib import Path

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


def run_migrations():
    conn = get_connection()
    cursor = conn.cursor()

    # V2: rule_definitions, rule_versions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rule_definitions (
          rule_id        VARCHAR(10)  NOT NULL,
          rule_type      VARCHAR(20)  NOT NULL,
          rule_name      VARCHAR(100) NOT NULL,
          is_skippable   BOOLEAN      NOT NULL DEFAULT FALSE,
          source         VARCHAR(10)  NOT NULL,
          active         BOOLEAN      NOT NULL DEFAULT TRUE,
          created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (rule_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rule_versions (
          version_id    CHAR(36)     NOT NULL,
          rule_id       VARCHAR(10)  NOT NULL,
          version_num   INT          NOT NULL,
          rule_config   JSON         NOT NULL,
          valid_from    DATETIME     NOT NULL,
          valid_to      DATETIME     NULL,
          changed_by    VARCHAR(100) NULL,
          change_reason TEXT         NULL,
          PRIMARY KEY (version_id),
          UNIQUE KEY uq_rule_version (rule_id, version_num),
          INDEX idx_rule_valid_from (rule_id, valid_from),
          CONSTRAINT fk_rv_rule FOREIGN KEY (rule_id)
            REFERENCES rule_definitions(rule_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    # V3: evaluation_runs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_runs (
          run_id          CHAR(36)     NOT NULL,
          request_id      VARCHAR(20)  NOT NULL,
          triggered_by    VARCHAR(20)  NOT NULL,
          agent_version   VARCHAR(30)  NOT NULL,
          started_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          finished_at     DATETIME     NULL,
          status          VARCHAR(20)  NOT NULL,
          final_outcome   VARCHAR(20)  NULL,
          output_snapshot JSON         NULL,
          parent_run_id   CHAR(36)     NULL,
          trigger_reason  VARCHAR(100) NULL,
          PRIMARY KEY (run_id),
          CONSTRAINT fk_er_request FOREIGN KEY (request_id)
            REFERENCES requests(request_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    # V4: hard_rule_checks, policy_checks
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hard_rule_checks (
          check_id      CHAR(36)     NOT NULL,
          run_id        CHAR(36)     NOT NULL,
          rule_id       VARCHAR(10)  NOT NULL,
          version_id    CHAR(36)     NOT NULL,
          supplier_id   VARCHAR(10)  NULL,
          skipped       BOOLEAN      NOT NULL DEFAULT FALSE,
          skip_reason   VARCHAR(200) NULL,
          result        VARCHAR(10)  NULL,
          actual_value  JSON         NULL,
          threshold     JSON         NULL,
          checked_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (check_id),
          INDEX idx_hrc_run_rule (run_id, rule_id),
          CONSTRAINT fk_hrc_run      FOREIGN KEY (run_id)      REFERENCES evaluation_runs(run_id),
          CONSTRAINT fk_hrc_rule     FOREIGN KEY (rule_id)     REFERENCES rule_definitions(rule_id),
          CONSTRAINT fk_hrc_version  FOREIGN KEY (version_id)  REFERENCES rule_versions(version_id),
          CONSTRAINT fk_hrc_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_checks (
          check_id        CHAR(36)     NOT NULL,
          run_id          CHAR(36)     NOT NULL,
          rule_id         VARCHAR(10)  NOT NULL,
          version_id      CHAR(36)     NOT NULL,
          supplier_id     VARCHAR(10)  NULL,
          result          VARCHAR(10)  NOT NULL,
          evidence        JSON         NOT NULL,
          override_by     VARCHAR(100) NULL,
          override_at     DATETIME     NULL,
          override_reason TEXT         NULL,
          checked_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (check_id),
          INDEX idx_pc_run_rule (run_id, rule_id),
          CONSTRAINT fk_pc_run      FOREIGN KEY (run_id)      REFERENCES evaluation_runs(run_id),
          CONSTRAINT fk_pc_rule     FOREIGN KEY (rule_id)     REFERENCES rule_definitions(rule_id),
          CONSTRAINT fk_pc_version  FOREIGN KEY (version_id)  REFERENCES rule_versions(version_id),
          CONSTRAINT fk_pc_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    # V5: supplier_evaluations
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS supplier_evaluations (
          eval_id              CHAR(36)     NOT NULL,
          run_id               CHAR(36)     NOT NULL,
          supplier_id          VARCHAR(10)  NOT NULL,
          `rank`               INT          NULL,
          total_score          DECIMAL(5,2) NULL,
          price_score          DECIMAL(5,2) NULL,
          quality_score        DECIMAL(5,2) NULL,
          esg_score            DECIMAL(5,2) NULL,
          risk_score           DECIMAL(5,2) NULL,
          hard_checks_total    INT          NOT NULL DEFAULT 0,
          hard_checks_passed   INT          NOT NULL DEFAULT 0,
          hard_checks_skipped  INT          NOT NULL DEFAULT 0,
          hard_checks_failed   INT          NOT NULL DEFAULT 0,
          policy_checks_total  INT          NOT NULL DEFAULT 0,
          policy_checks_passed INT          NOT NULL DEFAULT 0,
          policy_checks_warned INT          NOT NULL DEFAULT 0,
          policy_checks_failed INT          NOT NULL DEFAULT 0,
          excluded             BOOLEAN      NOT NULL DEFAULT FALSE,
          exclusion_rule_id    VARCHAR(10)  NULL,
          exclusion_reason     TEXT         NULL,
          pricing_snapshot     JSON         NULL,
          evaluated_at         DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (eval_id),
          CONSTRAINT fk_se_run       FOREIGN KEY (run_id)             REFERENCES evaluation_runs(run_id),
          CONSTRAINT fk_se_supplier  FOREIGN KEY (supplier_id)        REFERENCES suppliers(supplier_id),
          CONSTRAINT fk_se_excl_rule FOREIGN KEY (exclusion_rule_id)  REFERENCES rule_definitions(rule_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    # V8: rule_change_logs, policy_check_logs, evaluation_run_logs
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS rule_change_logs (
          log_id          CHAR(36)     NOT NULL,
          rule_id         VARCHAR(10)  NOT NULL,
          old_version_id  CHAR(36)     NULL,
          new_version_id  CHAR(36)     NOT NULL,
          changed_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          changed_by      VARCHAR(100) NOT NULL,
          change_reason   TEXT         NULL,
          affected_runs   JSON         NULL,
          PRIMARY KEY (log_id),
          INDEX idx_rcl_rule    (rule_id),
          INDEX idx_rcl_time    (changed_at),
          CONSTRAINT fk_rcl_rule        FOREIGN KEY (rule_id)        REFERENCES rule_definitions(rule_id),
          CONSTRAINT fk_rcl_new_version FOREIGN KEY (new_version_id) REFERENCES rule_versions(version_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_check_logs (
          log_id         CHAR(36)     NOT NULL,
          check_id       CHAR(36)     NOT NULL,
          run_id         CHAR(36)     NOT NULL,
          changed_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          changed_by     VARCHAR(100) NOT NULL,
          change_type    VARCHAR(30)  NOT NULL,
          old_result     VARCHAR(10)  NULL,
          new_result     VARCHAR(10)  NULL,
          old_evidence   JSON         NULL,
          new_evidence   JSON         NULL,
          override_reason TEXT        NULL,
          PRIMARY KEY (log_id),
          INDEX idx_pcl_check  (check_id),
          INDEX idx_pcl_run    (run_id),
          INDEX idx_pcl_time   (changed_at),
          CONSTRAINT fk_pcl_check FOREIGN KEY (check_id)
            REFERENCES policy_checks(check_id),
          CONSTRAINT fk_pcl_run FOREIGN KEY (run_id)
            REFERENCES evaluation_runs(run_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_run_logs (
          log_id         CHAR(36)     NOT NULL,
          run_id         CHAR(36)     NOT NULL,
          changed_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
          changed_by     VARCHAR(100) NOT NULL,
          change_type    VARCHAR(30)  NOT NULL,
          old_status     VARCHAR(20)  NULL,
          new_status     VARCHAR(20)  NULL,
          old_outcome    VARCHAR(20)  NULL,
          new_outcome    VARCHAR(20)  NULL,
          note           TEXT         NULL,
          PRIMARY KEY (log_id),
          INDEX idx_erl_run    (run_id),
          INDEX idx_erl_time   (changed_at),
          CONSTRAINT fk_erl_run FOREIGN KEY (run_id)
            REFERENCES evaluation_runs(run_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    conn.commit()

    # Seed rule_definitions (V6)
    cursor.execute("""
    INSERT IGNORE INTO rule_definitions (rule_id, rule_type, rule_name, is_skippable, source) VALUES
    ('HR-001', 'hard_rule',  'Budget ceiling check',                      TRUE,  'given'),
    ('HR-002', 'hard_rule',  'Delivery deadline feasibility',             TRUE,  'given'),
    ('HR-003', 'hard_rule',  'Supplier monthly capacity',                 TRUE,  'given'),
    ('HR-004', 'hard_rule',  'Minimum order quantity',                    TRUE,  'given'),
    ('HR-005', 'hard_rule',  'Pricing tier validity window',              TRUE,  'given'),
    ('HR-006', 'hard_rule',  'Quantity/text discrepancy',                 TRUE,  'given'),
    ('HR-007', 'hard_rule',  'Currency consistency',                      TRUE,  'custom'),
    ('PC-001', 'policy',     'Approval tier determination',               FALSE, 'given'),
    ('PC-002', 'policy',     'Quote count requirement',                   FALSE, 'given'),
    ('PC-003', 'policy',     'Preferred supplier check',                  FALSE, 'given'),
    ('PC-004', 'policy',     'Restricted supplier global',                FALSE, 'given'),
    ('PC-005', 'policy',     'Restricted supplier country-scoped',        FALSE, 'given'),
    ('PC-006', 'policy',     'Restricted supplier value-conditional',     FALSE, 'given'),
    ('PC-007', 'policy',     'Category sourcing rules',                   FALSE, 'given'),
    ('PC-008', 'policy',     'Data residency constraint',                 FALSE, 'given'),
    ('PC-009', 'policy',     'Geography/delivery compliance',             FALSE, 'given'),
    ('PC-010', 'policy',     'ESG requirement coverage',                  FALSE, 'given'),
    ('PC-011', 'policy',     'Supplier registration/sanction',            FALSE, 'given'),
    ('PC-012', 'policy',     'Preferred supplier category mismatch',      FALSE, 'custom'),
    ('PC-013', 'policy',     'Preferred supplier geo mismatch',           FALSE, 'custom'),
    ('ER-001', 'escalation', 'Missing required info',                     FALSE, 'given'),
    ('ER-002', 'escalation', 'Preferred supplier restricted',             FALSE, 'given'),
    ('ER-003', 'escalation', 'Contract value exceeds tier',               FALSE, 'given'),
    ('ER-004', 'escalation', 'No compliant supplier found',               FALSE, 'given'),
    ('ER-005', 'escalation', 'Data residency unsatisfiable',              FALSE, 'given'),
    ('ER-006', 'escalation', 'Quantity exceeds capacity',                 FALSE, 'given'),
    ('ER-007', 'escalation', 'Brand safety concern',                      FALSE, 'given'),
    ('ER-008', 'escalation', 'Supplier not registered/sanctioned',        FALSE, 'given'),
    ('ER-009', 'escalation', 'Contradictory request content',             FALSE, 'custom'),
    ('ER-010', 'escalation', 'Preferred supplier mismatch',               FALSE, 'custom')
    """)

    conn.commit()

    # Seed rule_versions only if none exist
    cursor.execute("SELECT COUNT(*) FROM rule_versions")
    if cursor.fetchone()[0] == 0:
        rules = [
            "HR-001", "HR-002", "HR-003", "HR-004", "HR-005", "HR-006", "HR-007",
            "PC-001", "PC-002", "PC-003", "PC-004", "PC-005", "PC-006", "PC-007",
            "PC-008", "PC-009", "PC-010", "PC-011", "PC-012", "PC-013",
            "ER-001", "ER-002", "ER-003", "ER-004", "ER-005", "ER-006",
            "ER-007", "ER-008", "ER-009", "ER-010",
        ]
        for rule_id in rules:
            cursor.execute(
                "INSERT INTO rule_versions (version_id, rule_id, version_num, rule_config, valid_from) "
                "VALUES (UUID(), %s, 1, '{\"check\":\"default\"}', NOW())",
                (rule_id,),
            )
        conn.commit()

    cursor.close()
    conn.close()
    print("Rule migrations completed successfully.")


if __name__ == "__main__":
    try:
        run_migrations()
    except mysql.connector.Error as e:
        print(f"\nDatabase error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)
