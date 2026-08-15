-- Seed Initial Administrator (password: admin123, hashed with bcrypt)
INSERT INTO users (id, email, username, hashed_password, full_name, role, is_active)
VALUES (
    'a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d',
    'admin@netvision.com',
    'admin',
    '$2b$12$A04joZlkeRv1o2NlE06o2.TRGL.koKQ8g9S1ZgxrKNPA6koJrNBCy', -- admin123 bcrypt hash
    'System Administrator',
    'ADMIN',
    TRUE
) ON CONFLICT DO NOTHING;

-- Seed Authorized Network Devices for initial monitoring tests
-- 1. Gateway Router
INSERT INTO devices (id, ip_address, hostname, name, description, device_type, is_authorized, monitoring_enabled, status, ping_interval, snmp_config, tcp_ports)
VALUES (
    'd1111111-1111-1111-1111-111111111111',
    '192.168.1.1',
    'gateway-router-01',
    'Gateway Router',
    'Primary Edge Router connecting to ISP',
    'router',
    TRUE,
    TRUE,
    'online',
    10,
    '{"version": "v2c", "community": "public", "port": 161}'::jsonb,
    '{80, 443}'::integer[]
) ON CONFLICT DO NOTHING;

-- 2. Core Ethernet Switch
INSERT INTO devices (id, ip_address, hostname, name, description, device_type, is_authorized, monitoring_enabled, status, ping_interval, snmp_config, tcp_ports)
VALUES (
    'd2222222-2222-2222-2222-222222222222',
    '192.168.1.2',
    'core-switch-02',
    'Core Switch',
    'Main backbone switch connecting all local servers',
    'switch',
    TRUE,
    TRUE,
    'online',
    15,
    '{"version": "v2c", "community": "public", "port": 161}'::jsonb,
    '{22, 23}'::integer[]
) ON CONFLICT DO NOTHING;

-- 3. Core Database Server
INSERT INTO devices (id, ip_address, hostname, name, description, device_type, is_authorized, monitoring_enabled, status, ping_interval, snmp_config, tcp_ports)
VALUES (
    'd3333333-3333-3333-3333-333333333333',
    '192.168.1.10',
    'database-srv-03',
    'Database Server',
    'PostgreSQL database server storing metrics history',
    'server',
    TRUE,
    TRUE,
    'online',
    30,
    '{}'::jsonb,
    '{5432, 22}'::integer[]
) ON CONFLICT DO NOTHING;

-- 4. Unauthorized rogue device (Detected but not approved yet)
INSERT INTO devices (id, ip_address, hostname, name, description, device_type, is_authorized, monitoring_enabled, status, ping_interval, snmp_config, tcp_ports)
VALUES (
    'd4444444-4444-4444-4444-444444444444',
    '192.168.1.155',
    'rogue-laptop-test',
    'Unknown Laptop',
    'Unidentified device connected to local port 5',
    'iot',
    FALSE,
    FALSE,
    'offline',
    60,
    '{}'::jsonb,
    '{}'::integer[]
) ON CONFLICT DO NOTHING;

-- Seed Network Topology Links
-- Connection: Router (192.168.1.1) to Core Switch (192.168.1.2)
INSERT INTO links (id, source_device_id, target_device_id, source_interface, target_interface, link_type, status)
VALUES (
    'c1111111-1111-1111-1111-111111111111',
    'd1111111-1111-1111-1111-111111111111',
    'd2222222-2222-2222-2222-222222222222',
    'GigabitEthernet0/1',
    'FastEthernet0/24',
    'fiber',
    'active'
) ON CONFLICT DO NOTHING;

-- Connection: Switch (192.168.1.2) to Database Server (192.168.1.10)
INSERT INTO links (id, source_device_id, target_device_id, source_interface, target_interface, link_type, status)
VALUES (
    'c2222222-2222-2222-2222-222222222222',
    'd2222222-2222-2222-2222-222222222222',
    'd3333333-3333-3333-3333-333333333333',
    'FastEthernet0/2',
    'eth0',
    'ethernet',
    'active'
) ON CONFLICT DO NOTHING;
