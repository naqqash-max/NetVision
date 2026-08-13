import pytest
from fastapi.testclient import TestClient
from uuid import uuid4
from app.main import app
from app.api.deps import require_viewer, require_operator, require_admin
from app.models.user import User

@pytest.fixture(autouse=True)
def bypass_auth():
    dummy_user = User(
        id="a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        email="admin@netvision.local",
        username="admin",
        role="ADMIN",
        is_active=True
    )
    app.dependency_overrides[require_viewer] = lambda: dummy_user
    app.dependency_overrides[require_operator] = lambda: dummy_user
    app.dependency_overrides[require_admin] = lambda: dummy_user
    yield
    app.dependency_overrides.clear()

from app.services.ping import ping_ipv4
from app.models.device import Device
from app.models.metric import PingLog

client = TestClient(app)

# Test targets
LOCALHOST_IP = "127.0.0.1"
UNREACHABLE_IP = "192.0.2.1"  # TEST-NET-1 documentation prefix, guaranteed to be unassigned
INVALID_IP = "999.999.999.999"

# ==========================================
# 1. UNIT TESTS (Network Engine ICMP Logic)
# ==========================================

@pytest.mark.asyncio
async def test_unit_successful_ping():
    """
    Test pinging a reliable local target (localhost).
    """
    result = await ping_ipv4(LOCALHOST_IP, timeout=1.0, count=2)
    assert result["is_online"] is True
    assert result["status"] == "online"
    assert result["packet_loss_pct"] == 0.0
    assert isinstance(result["latency_ms"], float)
    assert isinstance(result["min_latency"], float)
    assert isinstance(result["max_latency"], float)
    assert result["min_latency"] <= result["latency_ms"] <= result["max_latency"]
    assert result["error_msg"] is None

@pytest.mark.asyncio
async def test_unit_multiple_ping_attempts():
    """
    Test that the ping count parameter changes attempts correctly.
    """
    result = await ping_ipv4(LOCALHOST_IP, timeout=1.0, count=4)
    assert result["packet_loss_pct"] == 0.0
    # Average latency must represent the mean of successful pings
    assert result["latency_ms"] > 0

@pytest.mark.asyncio
async def test_unit_completely_unreachable_device():
    """
    Test pinging an unreachable IP target.
    """
    result = await ping_ipv4(UNREACHABLE_IP, timeout=0.5, count=2)
    assert result["is_online"] is False
    assert result["status"] == "offline"
    assert result["packet_loss_pct"] == 100.0
    assert result["latency_ms"] is None
    assert result["min_latency"] is None
    assert result["max_latency"] is None
    assert "timeout" in result["error_msg"].lower()

@pytest.mark.asyncio
async def test_unit_invalid_ip_address():
    """
    Test handling of invalid IP strings.
    """
    result = await ping_ipv4(INVALID_IP, timeout=1.0, count=1)
    assert result["is_online"] is False
    assert result["status"] == "offline"
    assert result["packet_loss_pct"] == 100.0
    assert "invalid" in result["error_msg"].lower()

# ==========================================
# 2. INTEGRATION TESTS (API & DB Integrations)
# ==========================================

def test_integration_manual_monitor_and_db_persistence():
    """
    Test creating a device, running an immediate check via API,
    verifying it writes to PostgreSQL, and retrieving the log metrics.
    """
    # 1. Create a clean test device on localhost
    test_device_payload = {
        "ip_address": LOCALHOST_IP,
        "hostname": "local-loopback",
        "name": "Local Loopback Interface",
        "description": "Local loopback testing node",
        "device_type": "server",
        "monitoring_enabled": True,
        "ping_interval": 30,
        "snmp_config": {},
        "tcp_ports": []
    }
    
    # Clean up any lingering local-loopback first
    all_devices = client.get("/api/v1/devices/").json()
    for d in all_devices:
        if d["ip_address"] == LOCALHOST_IP:
            client.delete(f"/api/v1/devices/{d['id']}")
            
    create_resp = client.post("/api/v1/devices/", json=test_device_payload)
    assert create_resp.status_code == 201
    device_data = create_resp.json()
    device_id = device_data["id"]
    
    # 2. Trigger manual ping check
    monitor_resp = client.post(f"/api/v1/devices/{device_id}/monitor")
    assert monitor_resp.status_code == 200
    monitor_data = monitor_resp.json()
    assert monitor_data["device_id"] == device_id
    assert monitor_data["is_online"] is True
    assert monitor_data["status"] == "online"
    assert monitor_data["packet_loss_pct"] == 0.0
    assert isinstance(monitor_data["latency_ms"], float)

    # 3. Verify status endpoint returns the updated values
    status_resp = client.get(f"/api/v1/devices/{device_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["device_id"] == device_id
    assert status_data["status"] == "online"
    assert status_data["is_online"] is True
    assert status_data["last_seen"] is not None

    # 4. Verify metrics endpoint retrieves the stored logs from Postgres
    metrics_resp = client.get(f"/api/v1/devices/{device_id}/metrics")
    assert metrics_resp.status_code == 200
    metrics_list = metrics_resp.json()
    assert isinstance(metrics_list, list)
    assert len(metrics_list) > 0
    
    latest_metric = metrics_list[0]
    assert latest_metric["device_id"] == device_id
    assert latest_metric["status"] == "online"
    assert latest_metric["packet_loss_pct"] == 0.0
    assert abs(latest_metric["latency_ms"] - monitor_data["latency_ms"]) < 1e-4
    assert abs(latest_metric["min_latency"] - monitor_data["min_latency"]) < 1e-4
    assert abs(latest_metric["max_latency"] - monitor_data["max_latency"]) < 1e-4
    assert latest_metric["error_msg"] is None
    
    # 5. Clean up testing device
    delete_resp = client.delete(f"/api/v1/devices/{device_id}")
    assert delete_resp.status_code == 204

def test_integration_unregistered_device_checks():
    """
    Test triggering monitoring endpoints with random or unauthorized UUIDs.
    """
    random_uuid = str(uuid4())
    
    # Verify GET status fails with 404
    status_resp = client.get(f"/api/v1/devices/{random_uuid}/status")
    assert status_resp.status_code == 404
    
    # Verify GET metrics fails with 404
    metrics_resp = client.get(f"/api/v1/devices/{random_uuid}/metrics")
    assert metrics_resp.status_code == 404
    
    # Verify POST monitor fails with 404
    monitor_resp = client.post(f"/api/v1/devices/{random_uuid}/monitor")
    assert monitor_resp.status_code == 404
