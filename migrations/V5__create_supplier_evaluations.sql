-- V5: Create supplier_evaluations table
-- Depends on: evaluation_runs, suppliers, rule_definitions

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
