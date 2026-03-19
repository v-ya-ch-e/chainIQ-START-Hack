-- V8: Proper audit logging for all mutable post-creation changes
-- Replaces V7 approach. V7 is kept as-is (escalation_logs audit trail for escalations).
-- This adds equivalent audit trails for evaluation_runs and policy_checks.
-- Also adds `parent_run_id` to evaluation_runs to chain re-evaluations.
--
-- Philosophy:
--   - operational tables (escalations, evaluation_runs, policy_checks) are the
--     current state of record
--   - *_logs tables are append-only audit trails — never updated, never deleted
--   - every human-initiated change writes a log row before mutating the source row
--   - re-evaluations INSERT a new evaluation_runs row (new run_id) and link via
--     parent_run_id so the full chain is queryable

-- ── Step 1: Add parent_run_id to evaluation_runs ─────────────────
-- Links a re-evaluation run back to the run that triggered it.
-- NULL = original run. Non-null = triggered by escalation or manual re-check.
-- Idempotent: ignores "Duplicate column" if already added.

DELIMITER //
CREATE PROCEDURE _v8_add_eval_run_columns()
BEGIN
  DECLARE CONTINUE HANDLER FOR 1060 BEGIN END;  -- Duplicate column name

  ALTER TABLE evaluation_runs ADD COLUMN parent_run_id  CHAR(36)     NULL;
  ALTER TABLE evaluation_runs ADD COLUMN trigger_reason VARCHAR(100) NULL;
END//
DELIMITER ;
CALL _v8_add_eval_run_columns();
DROP PROCEDURE _v8_add_eval_run_columns;
-- trigger_reason: 'initial' | 'rule_change' | 'escalation_resolved' |
--                 'missing_info_supplied' | 'manual_recheck'

-- ── Step 2: evaluation_run_logs ───────────────────────────────────
-- Audit trail for every status/outcome change on an evaluation run.
-- Written before the UPDATE on evaluation_runs.

CREATE TABLE IF NOT EXISTS evaluation_run_logs (
  log_id         CHAR(36)     NOT NULL,
  run_id         CHAR(36)     NOT NULL,
  changed_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  changed_by     VARCHAR(100) NOT NULL,
  -- 'agent' | 'user:<id>' | 'system'
  change_type    VARCHAR(30)  NOT NULL,
  -- 'status_change' | 'outcome_override' | 'rerun_triggered'
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ── Step 3: policy_check_logs ─────────────────────────────────────
-- Audit trail for human overrides on policy checks.
-- policy_checks.override_by/override_at/override_reason store current state.
-- This table stores the full history if a check is overridden more than once.

CREATE TABLE IF NOT EXISTS policy_check_logs (
  log_id         CHAR(36)     NOT NULL,
  check_id       CHAR(36)     NOT NULL,
  run_id         CHAR(36)     NOT NULL,
  changed_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  changed_by     VARCHAR(100) NOT NULL,
  change_type    VARCHAR(30)  NOT NULL,
  -- 'override_applied' | 'override_reversed' | 'result_changed'
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- ── Step 4: rule_change_logs ──────────────────────────────────────
-- Audit trail for rule version changes.
-- rule_versions is already insert-only, but this records WHO triggered
-- each version change and optionally which runs were affected.

CREATE TABLE IF NOT EXISTS rule_change_logs (
  log_id          CHAR(36)     NOT NULL,
  rule_id         VARCHAR(10)  NOT NULL,
  old_version_id  CHAR(36)     NULL,
  -- NULL for the initial v1 seed
  new_version_id  CHAR(36)     NOT NULL,
  changed_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  changed_by      VARCHAR(100) NOT NULL,
  change_reason   TEXT         NULL,
  affected_runs   JSON         NULL,
  -- optional: list of run_ids that were using old version at time of change
  -- e.g. ["run-uuid-1", "run-uuid-2"] — useful for impact analysis
  PRIMARY KEY (log_id),
  INDEX idx_rcl_rule    (rule_id),
  INDEX idx_rcl_time    (changed_at),
  CONSTRAINT fk_rcl_rule        FOREIGN KEY (rule_id)        REFERENCES rule_definitions(rule_id),
  CONSTRAINT fk_rcl_new_version FOREIGN KEY (new_version_id) REFERENCES rule_versions(version_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;