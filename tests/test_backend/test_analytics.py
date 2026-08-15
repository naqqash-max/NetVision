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

def test_get_noc_summary():
    response = client.get("/api/v1/analytics/noc-summary")
    assert response.status_code == 200
    data = response.json()

    assert "total_devices" in data
    assert "online_devices" in data
    assert "offline_devices" in data
    assert "degraded_devices" in data
    assert "active_alerts_count" in data
    assert "critical_alerts_count" in data
    assert "warning_alerts_count" in data
    assert "network_health_score" in data
    assert 0.0 <= data["network_health_score"] <= 100.0

def test_get_historical_analytics_ranges():
    for time_range in ["15m", "1h", "6h", "24h", "7d"]:
        response = client.get(f"/api/v1/analytics/history?time_range={time_range}")
        assert response.status_code == 200
        data = response.json()

        assert data["time_range"] == time_range
        assert "icmp_metrics" in data
        assert "tcp_metrics" in data
        assert "snmp_metrics" in data
        assert isinstance(data["icmp_metrics"], list)
        assert isinstance(data["tcp_metrics"], list)
        assert isinstance(data["snmp_metrics"], list)

def test_get_historical_analytics_device_filter():
    devices_response = client.get("/api/v1/devices/")
    assert devices_response.status_code == 200
    devices = devices_response.json()

    if devices:
        device_id = devices[0]["id"]
        response = client.get(f"/api/v1/analytics/history?time_range=1h&device_id={device_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "1h"
