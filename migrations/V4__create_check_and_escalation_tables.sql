-- V4: Create hard_rule_checks, policy_checks, escalation_logs
-- Depends on: evaluation_runs, rule_definitions, rule_versions, suppliers
--
-- Traceability: trigger_table + trigger_check_id link each escalation to the
-- exact hard_rule_check or policy_check that triggered it (audit requirement).

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS escalation_logs (
  escalation_id       CHAR(36)     NOT NULL,
  run_id              CHAR(36)     NOT NULL,
  rule_id             VARCHAR(10)  NOT NULL,
  version_id          CHAR(36)     NOT NULL,
  trigger_table       VARCHAR(30)  NOT NULL,
  trigger_check_id    CHAR(36)     NOT NULL,
  escalation_target   VARCHAR(100) NOT NULL,
  escalation_reason   TEXT         NOT NULL,
  event_type          VARCHAR(50)  NOT NULL,
  event_dispatched_at DATETIME     NULL,
  event_payload       JSON         NULL,
  event_status        VARCHAR(20)  NOT NULL DEFAULT 'pending',
  status              VARCHAR(20)  NOT NULL DEFAULT 'open',
  resolved_by         VARCHAR(100) NULL,
  resolved_at         DATETIME     NULL,
  resolution_note     TEXT         NULL,
  created_at          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (escalation_id),
  INDEX idx_el_run_rule     (run_id, rule_id),
  INDEX idx_el_event_status (event_status),
  CONSTRAINT fk_el_run     FOREIGN KEY (run_id)      REFERENCES evaluation_runs(run_id),
  CONSTRAINT fk_el_rule    FOREIGN KEY (rule_id)     REFERENCES rule_definitions(rule_id),
  CONSTRAINT fk_el_version FOREIGN KEY (version_id)  REFERENCES rule_versions(version_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
