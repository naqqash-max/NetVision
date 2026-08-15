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
        email="admin@netvision.com",
        username="admin",
        role="ADMIN",
        is_active=True
    )
    app.dependency_overrides[require_viewer] = lambda: dummy_user
    app.dependency_overrides[require_operator] = lambda: dummy_user
    app.dependency_overrides[require_admin] = lambda: dummy_user
    yield
    app.dependency_overrides.clear()

client = TestClient(app)

# Helper device template
TEST_IP = "192.168.99.99"
TEST_DEVICE_PAYLOAD = {
    "ip_address": TEST_IP,
    "hostname": "test-router-99",
    "name": "Temporary Test Router",
    "description": "Integration test device instance",
    "device_type": "router",
    "monitoring_enabled": True,
    "ping_interval": 10,
    "snmp_config": {"version": "v2c", "community": "private", "port": 161},
    "tcp_ports": [22, 80]
}

def test_create_device():
    # 1. Ensure any lingering test device is cleaned up first
    all_devices = client.get("/api/v1/devices/").json()
    for d in all_devices:
        if d["ip_address"] == TEST_IP:
            client.delete(f"/api/v1/devices/{d['id']}")

    # 2. Test successful creation
    response = client.post("/api/v1/devices/", json=TEST_DEVICE_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["ip_address"] == TEST_IP
    assert data["hostname"] == "test-router-99"
    assert data["name"] == "Temporary Test Router"
    assert data["device_type"] == "router"
    assert data["status"] == "offline"  # Default status
    assert "id" in data

def test_get_all_devices():
    response = client.get("/api/v1/devices/")
    assert response.status_code == 200
    devices = response.json()
    assert isinstance(devices, list)
    assert len(devices) > 0
    # Confirm our test device is visible in the collection
    ips = [d["ip_address"] for d in devices]
    assert TEST_IP in ips

def test_get_individual_device():
    # Find test device ID
    all_devices = client.get("/api/v1/devices/").json()
    test_device = next(d for d in all_devices if d["ip_address"] == TEST_IP)
    device_id = test_device["id"]

    response = client.get(f"/api/v1/devices/{device_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == device_id
    assert data["ip_address"] == TEST_IP

def test_update_device():
    # Find test device ID
    all_devices = client.get("/api/v1/devices/").json()
    test_device = next(d for d in all_devices if d["ip_address"] == TEST_IP)
    device_id = test_device["id"]

    # Perform update
    update_payload = {
        "name": "Updated Test Router Name",
        "ping_interval": 60,
        "tcp_ports": [22, 80, 443]
    }
    response = client.put(f"/api/v1/devices/{device_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Test Router Name"
    assert data["ping_interval"] == 60
    assert data["tcp_ports"] == [22, 80, 443]

def test_delete_device():
    # Find test device ID
    all_devices = client.get("/api/v1/devices/").json()
    test_device = next(d for d in all_devices if d["ip_address"] == TEST_IP)
    device_id = test_device["id"]

    # Delete
    response = client.delete(f"/api/v1/devices/{device_id}")
    assert response.status_code == 204

    # Verify it is gone
    verify_response = client.get(f"/api/v1/devices/{device_id}")
    assert verify_response.status_code == 404

def test_invalid_ipv4_address():
    # Attempt to create with invalid IP format
    bad_payload = TEST_DEVICE_PAYLOAD.copy()
    bad_payload["ip_address"] = "invalid ip!"  # Space and exclamation mark fail regex
    response = client.post("/api/v1/devices/", json=bad_payload)
    assert response.status_code == 422  # Pydantic validation error

    bad_payload["ip_address"] = "not@valid"  # @ fails regex
    response = client.post("/api/v1/devices/", json=bad_payload)
    assert response.status_code == 422

def test_non_existent_device():
    random_id = str(uuid4())
    response = client.get(f"/api/v1/devices/{random_id}")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_database_error_duplicate_ip():
    # 1. Create a device
    client.post("/api/v1/devices/", json=TEST_DEVICE_PAYLOAD)
    
    # 2. Attempt to create another device with the SAME IP to force database constraint conflict
    duplicate_payload = TEST_DEVICE_PAYLOAD.copy()
    duplicate_payload["hostname"] = "another-host"
    response = client.post("/api/v1/devices/", json=duplicate_payload)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"].lower()

    # 3. Clean up the device
    all_devices = client.get("/api/v1/devices/").json()
    test_device = next(d for d in all_devices if d["ip_address"] == TEST_IP)
    client.delete(f"/api/v1/devices/{test_device['id']}")
