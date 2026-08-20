# NetVision Data Retention & Auto-Pruning Strategy

This document outlines the proposed historical monitoring data retention policy and automatic pruning strategy for the NetVision platform. Since the application continuously monitors devices via ICMP (Ping), TCP Ports, and SNMP, the database logs tables (`ping_log`, `port_log`, `snmp_log`) grow indefinitely. A structured pruning strategy is required to maintain database performance, prevent disk exhaustion, and keep query indexes small.

---

## 1. Retention Policy Configuration

We propose a tiered retention policy based on the data utility and granularity over time:

| Data Type | Table Name | Recommended Retention Window | Rationale |
| :--- | :--- | :--- | :--- |
| **Ping Logs** | `ping_log` | 30 Days | High-frequency telemetry. Detailed logs are rarely needed after 30 days. |
| **Port Logs** | `port_log` | 30 Days | High-frequency service availability checks. |
| **SNMP Logs** | `snmp_log` | 90 Days | Telemetry is crucial for long-term capacity planning and bandwidth analysis. |
| **Alert Logs** | `alert` | 180 Days | System incident logs must be retained longer for SLA and audit compliance. |

These retention thresholds will be configurable via environment variables in production:
* `RETENTION_PING_DAYS=30`
* `RETENTION_PORT_DAYS=30`
* `RETENTION_SNMP_DAYS=90`
* `RETENTION_ALERT_DAYS=180`

---

## 2. Automated Pruning Mechanisms

To execute data pruning efficiently without impacting live system operations, two distinct paths are proposed depending on database scale:

### Option A: Scheduler-Driven Batch Pruning (Default / Small-to-Medium Deployments)
We can utilize the existing `MonitorScheduler` background daemon to trigger an automatic batch-delete routine once every 24 hours (e.g., at 02:00 AM system time).

* **Mechanism**:
  Execute SQL queries with `LIMIT` clauses in a loop to delete records in batches of 1,000 to 5,000. This prevents locking tables and avoids long-running transaction blockages.
* **SQL Query Pattern**:
  ```sql
  -- Run in a loop until rows affected = 0
  DELETE FROM ping_log 
  WHERE timestamp < NOW() - INTERVAL '30 days'
  AND id IN (
      SELECT id FROM ping_log 
      WHERE timestamp < NOW() - INTERVAL '30 days'
      LIMIT 1000
  );
  ```

### Option B: Time-Scale / Declarative Partitioning (Recommended for Large Deployments)
For large-scale deployments monitoring hundreds of devices, running `DELETE` statements on millions of rows is slow and fragments database tables. We recommend PostgreSQL Declarative Partitioning based on the `timestamp` column.

* **Mechanism**:
  * Partition tables by range (e.g., monthly partitions: `ping_log_y2026m08`, `ping_log_y2026m09`).
  * Drop old partitions at the end of the retention period. Dropping a partition table is a fast `DROP TABLE` metadata operation that instantly frees disk space and generates zero transaction log overhead.
* **Implementation Pattern**:
  ```sql
  -- Parent table definition
  CREATE TABLE ping_log (
      id BIGSERIAL,
      device_id UUID NOT NULL,
      latency_ms REAL,
      min_latency REAL,
      max_latency REAL,
      packet_loss_pct REAL NOT NULL,
      is_online BOOLEAN NOT NULL,
      status VARCHAR(20) NOT NULL,
      error_msg TEXT,
      timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
      PRIMARY KEY (id, timestamp)
  ) PARTITION BY RANGE (timestamp);
  ```

---

## 3. Index Optimization for Pruning

To keep pruning and query operations extremely fast, index optimization is critical. The following database indexes must be maintained:

1. **Ping Logs Index**:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_ping_log_timestamp_device 
   ON ping_log (timestamp, device_id);
   ```
   * *Purpose*: Speeds up range-based queries (NOC Dashboard, Reports) and enables fast scanning for the pruning deletion process.

2. **Port Logs Index**:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_port_log_timestamp_device 
   ON port_log (timestamp, device_id);
   ```

3. **SNMP Logs Index**:
   ```sql
   CREATE INDEX IF NOT EXISTS idx_snmp_log_timestamp_device 
   ON snmp_log (timestamp, device_id);
   ```

---

## 4. Implementation Action Plan

1. **Step 1**: Add environment variables in `backend/app/core/config.py` defining the retention limits.
2. **Step 2**: Add index migration script using Alembic.
3. **Step 3**: Implement a daily cleanup worker task inside `networking-engine` or as an independent celery/cron container that performs batch deletions.
