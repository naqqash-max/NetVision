-- =============================================================================
-- Migration: 001_indexes.sql
-- Description: Add timestamp-leading indexes for range-based report aggregation
--              and telemetry retention pruning.
-- Reversible: Yes
-- =============================================================================

-- -----------------------------------------------------------------------------
-- [ UP ]: Apply Indexes
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_ping_logs_timestamp_device ON ping_logs (timestamp, device_id);
CREATE INDEX IF NOT EXISTS idx_port_logs_timestamp_device ON port_logs (timestamp, device_id);
CREATE INDEX IF NOT EXISTS idx_snmp_logs_timestamp_device ON snmp_logs (timestamp, device_id);

-- -----------------------------------------------------------------------------
-- [ DOWN ]: Revert Indexes
-- -----------------------------------------------------------------------------
-- DROP INDEX IF EXISTS idx_ping_logs_timestamp_device;
-- DROP INDEX IF EXISTS idx_port_logs_timestamp_device;
-- DROP INDEX IF EXISTS idx_snmp_logs_timestamp_device;
