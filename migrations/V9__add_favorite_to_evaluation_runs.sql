-- V9: Add favorite column to evaluation_runs
-- Allows users to mark evaluation runs as favorites for quick access.

ALTER TABLE evaluation_runs ADD COLUMN favorite BOOLEAN NOT NULL DEFAULT FALSE;
