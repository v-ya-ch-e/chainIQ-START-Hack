-- V3: Create evaluation_runs table (depends on requests)
--
-- output_snapshot: Full agent output (request_interpretation, validation,
-- supplier_shortlist, escalations, audit_trail) per example_output.json.
-- Enables audit replay and traceability of what the agent produced.

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
  PRIMARY KEY (run_id),
  CONSTRAINT fk_er_request FOREIGN KEY (request_id)
    REFERENCES requests(request_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
