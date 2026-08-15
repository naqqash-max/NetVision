-- Enable UUID generation extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. Users Table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    role VARCHAR(50) NOT NULL DEFAULT 'VIEWER',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    password_changed_at TIMESTAMP WITH TIME ZONE
);


-- 2. Devices Table
CREATE TABLE IF NOT EXISTS devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ip_address VARCHAR(45) UNIQUE NOT NULL,
    hostname VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    description TEXT,
    device_type VARCHAR(50) DEFAULT 'server', -- router, switch, server, firewall, iot
    is_authorized BOOLEAN DEFAULT FALSE,
    monitoring_enabled BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'offline', -- online, offline, degraded
    ping_interval INTEGER DEFAULT 30, -- default polling interval in seconds
    snmp_config JSONB DEFAULT '{}'::jsonb, -- {"version": "v2c", "community": "public", "port": 161}
    tcp_ports INTEGER[] DEFAULT '{}'::INTEGER[], -- ports array: e.g., {22, 80, 443}
    last_seen TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 3. Topology Links Table (Mapping interconnections)
CREATE TABLE IF NOT EXISTS links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    target_device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    source_interface VARCHAR(100),
    target_interface VARCHAR(100),
    link_type VARCHAR(50) DEFAULT 'ethernet',
    status VARCHAR(20) DEFAULT 'active',
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Ping Logs Table (Time-Series Metric)
CREATE TABLE IF NOT EXISTS ping_logs (
    id BIGSERIAL PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    latency_ms REAL, -- Average latency
    min_latency REAL,
    max_latency REAL,
    packet_loss_pct REAL NOT NULL,
    is_online BOOLEAN NOT NULL,
    status VARCHAR(20) DEFAULT 'offline', -- online, offline, degraded
    error_msg TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ping_logs_device_timestamp ON ping_logs(device_id, timestamp DESC);

-- 5. Port Logs Table (Time-Series Metric)
CREATE TABLE IF NOT EXISTS port_logs (
    id BIGSERIAL PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    port INTEGER NOT NULL,
    is_open BOOLEAN NOT NULL,
    response_time_ms REAL,
    status VARCHAR(50) DEFAULT 'closed',
    error_msg TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_port_logs_device_timestamp ON port_logs(device_id, timestamp DESC);

-- 6. SNMP Logs Table (Time-Series Metric)
CREATE TABLE IF NOT EXISTS snmp_logs (
    id BIGSERIAL PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    metrics JSONB NOT NULL, -- {"cpu_util": 23.4, "mem_util": 55.6, "uptime": 3600}
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_snmp_logs_device_timestamp ON snmp_logs(device_id, timestamp DESC);

-- 7. Alerts Table
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- info, warning, critical
    status VARCHAR(20) DEFAULT 'OPEN', -- OPEN, ACKNOWLEDGED, RESOLVED
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    monitored_resource VARCHAR(255),
    current_value VARCHAR(255),
    threshold VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    resolved_at TIMESTAMP WITH TIME ZONE,
    details JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_device_id ON alerts(device_id);
CREATE INDEX IF NOT EXISTS idx_alerts_type ON alerts(alert_type);

-- 8. Global Settings Table
CREATE TABLE IF NOT EXISTS global_settings (
    key VARCHAR(100) PRIMARY KEY,
    value VARCHAR(255) NOT NULL,
    description TEXT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 9. Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    username VARCHAR(255),
    action VARCHAR(100) NOT NULL,
    details TEXT,
    ip_address VARCHAR(45),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- 10. Password Reset Tokens Table
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token_hash ON password_reset_tokens(token_hash);

