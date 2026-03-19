-- V2: Create rule_definitions and rule_versions tables

CREATE TABLE IF NOT EXISTS rule_definitions (
  rule_id        VARCHAR(10)  NOT NULL,
  rule_type      VARCHAR(20)  NOT NULL,
  rule_name      VARCHAR(100) NOT NULL,
  is_skippable   BOOLEAN      NOT NULL DEFAULT FALSE,
  source         VARCHAR(10)  NOT NULL,
  active         BOOLEAN      NOT NULL DEFAULT TRUE,
  created_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (rule_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
