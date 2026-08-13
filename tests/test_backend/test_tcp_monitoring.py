import socket
import threading
import time
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

from app.services.tcp_monitor import check_port_sync, check_device_ports
from app.models.device import Device
from app.models.metric import PortLog
from app.core.db import get_db

client = TestClient(app)

LOCALHOST_IP = "127.0.0.1"
UNREACHABLE_IP = "192.0.2.1"  # TEST-NET-1, drops packets

@pytest.fixture(scope="module")
def local_tcp_server():
    """
    Spins up a lightweight local TCP server in a background thread to mock an open port.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((LOCALHOST_IP, 0))
    host, port = sock.getsockname()
    sock.listen(5)
    
    stop_event = threading.Event()
    
    def run_server():
        sock.settimeout(0.2)
        while not stop_event.is_set():
            try:
                conn, addr = sock.accept()
                conn.close()
            except socket.timeout:
                continue
            except Exception:
                break
        sock.close()
        
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    
    yield host, port
    
    stop_event.set()
    thread.join()


# ==========================================
# 1. UNIT TESTS (Network Engine TCP Logic)
# ==========================================

def test_unit_open_tcp_port(local_tcp_server):
    """
    Test checking a port that is open on localhost.
    """
    host, port = local_tcp_server
    result = check_port_sync(host, port, timeout=1.0)
    assert result["is_open"] is True
    assert result["status"] == "open"
    assert result["port"] == port
    assert isinstance(result["response_time_ms"], float)
    assert result["response_time_ms"] > 0
    assert result["error_msg"] is None

def test_unit_closed_tcp_port():
    """
    Test checking a closed port on localhost (e.g. 59999).
    """
    # Pick a port that is highly unlikely to be open
    result = check_port_sync(LOCALHOST_IP, 59999, timeout=1.0)
    assert result["is_open"] is False
    assert result["status"] == "closed"
    assert result["port"] == 59999
    assert result["response_time_ms"] is None
    assert "refused" in result["error_msg"].lower() or "closed" in result["error_msg"].lower()

def test_unit_connection_timeout():
    """
    Test connection timeout by connecting to an unreachable IP.
    """
    result = check_port_sync(UNREACHABLE_IP, 80, timeout=0.2)
    assert result["is_open"] is False
    assert result["status"] in ("timeout", "unreachable")
    assert result["response_time_ms"] is None
    if result["status"] == "timeout":
        assert "timeout" in result["error_msg"].lower() or "timed out" in result["error_msg"].lower()

@pytest.mark.asyncio
async def test_unit_invalid_port_number():
    """
    Test validating port numbers (1-65535).
    """
    results = await check_device_ports(LOCALHOST_IP, [0, 80, 70000])
    # Port 0: invalid
    assert results[0]["port"] == 0
    assert results[0]["status"] == "error"
    assert "invalid" in results[0]["error_msg"].lower()

    # Port 80: valid (checked)
    assert results[1]["port"] == 80

    # Port 70000: invalid
    assert results[2]["port"] == 70000
    assert results[2]["status"] == "error"
    assert "invalid" in results[2]["error_msg"].lower()

@pytest.mark.asyncio
async def test_unit_multiple_configured_ports(local_tcp_server):
    """
    Test checking multiple ports asynchronously.
    """
    host, port = local_tcp_server
    results = await check_device_ports(host, [port, 59999])
    assert len(results) == 2
    # Local open port
    assert results[0]["port"] == port
    assert results[0]["status"] == "open"
    # Closed port
    assert results[1]["port"] == 59999
    assert results[1]["status"] == "closed"


# ==========================================
# 2. INTEGRATION TESTS (API & DB Persistence)
# ==========================================

def test_api_check_unregistered_device():
    """
    Test manual port check returns 404 for an unregistered device.
    """
    random_uuid = str(uuid4())
    response = client.post(f"/api/v1/devices/{random_uuid}/ports/check")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_api_check_and_persistence(local_tcp_server):
    """
    Test manual port check and persistence to PostgreSQL.
    """
    host, port = local_tcp_server
    # 1. Create a dummy device in database with the open port and a closed port
    device_data = {
        "ip_address": host,
        "hostname": "tcp-test-device.local",
        "name": "TCP Test Device",
        "description": "Integration testing node for TCP service scans",
        "device_type": "server",
        "monitoring_enabled": True,
        "tcp_ports": [port, 59999]
    }
    
    # Register device
    reg_response = client.post("/api/v1/devices/", json=device_data)
    assert reg_response.status_code == 201
    device = reg_response.json()
    device_id = device["id"]

    # Authorize device
    auth_response = client.put(f"/api/v1/devices/{device_id}", json={"is_authorized": True})
    assert auth_response.status_code == 200

    # 2. Trigger immediate TCP port check endpoint
    check_response = client.post(f"/api/v1/devices/{device_id}/ports/check")
    assert check_response.status_code == 200
    check_results = check_response.json()
    
    assert len(check_results) == 2
    # Open port check
    assert check_results[0]["port"] == port
    assert check_results[0]["is_open"] is True
    assert check_results[0]["status"] == "open"
    assert isinstance(check_results[0]["response_time_ms"], float)
    
    # Closed port check
    assert check_results[1]["port"] == 59999
    assert check_results[1]["is_open"] is False
    assert check_results[1]["status"] == "closed"

    # 3. Retrieve latest status from GET /api/v1/devices/{device_id}/ports
    status_response = client.get(f"/api/v1/devices/{device_id}/ports")
    assert status_response.status_code == 200
    statuses = status_response.json()
    assert len(statuses) == 2
    
    # Assert correct statuses are mapped
    assert statuses[0]["port"] == port
    assert statuses[0]["status"] == "open"
    assert statuses[0]["is_open"] is True
    
    assert statuses[1]["port"] == 59999
    assert statuses[1]["status"] == "closed"
    assert statuses[1]["is_open"] is False

    # 4. Retrieve historical metrics from GET /api/v1/devices/{device_id}/ports/metrics
    metrics_response = client.get(f"/api/v1/devices/{device_id}/ports/metrics")
    assert metrics_response.status_code == 200
    metrics = metrics_response.json()
    # At least two check logs should exist
    assert len(metrics) >= 2
    assert metrics[0]["device_id"] == device_id
    
    # Clean up device
    del_response = client.delete(f"/api/v1/devices/{device_id}")
    assert del_response.status_code == 204
