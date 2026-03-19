-- V7: Restructure escalation tables
-- - Rename escalation_logs → escalations (main escalation entity, linked to rule)
-- - Create escalation_logs (audit trail: logs changes to escalations, when and by whom)
--
-- escalations: the escalation entity (triggered by a rule/policy check)
-- escalation_logs: audit trail for changes (status updates, resolution, etc.)
-- Idempotent: only renames if escalations does not yet exist.

DELIMITER //
CREATE PROCEDURE _v7_restructure_escalations()
BEGIN
  IF (SELECT COUNT(*) FROM information_schema.tables
      WHERE table_schema = DATABASE() AND table_name = 'escalations') = 0
     AND (SELECT COUNT(*) FROM information_schema.tables
          WHERE table_schema = DATABASE() AND table_name = 'escalation_logs') > 0
  THEN
    RENAME TABLE escalation_logs TO escalations;
  END IF;
END//
DELIMITER ;
CALL _v7_restructure_escalations();
DROP PROCEDURE _v7_restructure_escalations;

-- Step 2: Create new escalation_logs as audit trail for escalations
CREATE TABLE IF NOT EXISTS escalation_logs (
  log_id         CHAR(36)     NOT NULL,
  escalation_id   CHAR(36)     NOT NULL,
  changed_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  changed_by      VARCHAR(100) NOT NULL,
  change_type     VARCHAR(30)  NOT NULL,
  field_changed   VARCHAR(50)  NULL,
  old_value       JSON         NULL,
  new_value       JSON         NULL,
  note            TEXT         NULL,
  PRIMARY KEY (log_id),
  INDEX idx_elog_escalation (escalation_id),
  INDEX idx_elog_changed_at (changed_at),
  CONSTRAINT fk_elog_escalation FOREIGN KEY (escalation_id)
    REFERENCES escalations(escalation_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
