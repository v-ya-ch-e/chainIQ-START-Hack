-- V1: Add UUID columns to requests and suppliers for audit trail linkage
-- Prerequisites: requests and suppliers tables must exist
-- Idempotent: ignores "Duplicate column" if uuid already exists

DELIMITER //
CREATE PROCEDURE _v1_add_uuids()
BEGIN
  DECLARE CONTINUE HANDLER FOR 1060 BEGIN END;  -- Duplicate column name

  ALTER TABLE requests ADD COLUMN uuid CHAR(36) NULL UNIQUE;
  UPDATE requests SET uuid = UUID() WHERE uuid IS NULL;
  ALTER TABLE requests MODIFY COLUMN uuid CHAR(36) NOT NULL UNIQUE;

  ALTER TABLE suppliers ADD COLUMN uuid CHAR(36) NULL UNIQUE;
  UPDATE suppliers SET uuid = UUID() WHERE uuid IS NULL;
  ALTER TABLE suppliers MODIFY COLUMN uuid CHAR(36) NOT NULL UNIQUE;
END//
DELIMITER ;
CALL _v1_add_uuids();
DROP PROCEDURE _v1_add_uuids;
