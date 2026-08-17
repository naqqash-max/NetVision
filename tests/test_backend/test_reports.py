import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
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

# 1. Test Network Health Report API
def test_get_network_health_report_json():
    response = client.get("/api/v1/reports/network-health?time_range=24h")
    assert response.status_code == 200
    data = response.json()

    assert "network_health_score" in data
    assert "total_devices" in data
    assert "online_devices" in data
    assert "degraded_devices" in data
    assert "offline_devices" in data
    assert 0.0 <= data["network_health_score"] <= 100.0


def test_get_network_health_report_csv():
    response = client.get("/api/v1/reports/network-health?time_range=24h&format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert "Network Health Score" in response.text


def test_get_network_health_report_pdf():
    response = client.get("/api/v1/reports/network-health?time_range=24h&format=pdf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")


# 2. Test Device Availability Report API
def test_get_device_availability_report_json():
    response = client.get("/api/v1/reports/device-availability?time_range=1h")
    assert response.status_code == 200
    data = response.json()

    assert "total_devices" in data
    assert "avg_availability_pct" in data
    assert "items" in data
    assert isinstance(data["items"], list)


def test_get_device_availability_report_csv_and_pdf():
    csv_resp = client.get("/api/v1/reports/device-availability/csv?time_range=6h")
    assert csv_resp.status_code == 200
    assert csv_resp.headers["content-type"].startswith("text/csv")

    pdf_resp = client.get("/api/v1/reports/device-availability/pdf?time_range=6h")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF-")


# 3. Test Alert Report API
def test_get_alert_report_json():
    response = client.get("/api/v1/reports/alerts?time_range=24h")
    assert response.status_code == 200
    data = response.json()

    assert "total_incidents" in data
    assert "critical_incidents" in data
    assert "warning_incidents" in data
    assert "info_incidents" in data
    assert "items" in data


def test_get_alert_report_filtering():
    response = client.get("/api/v1/reports/alerts?severity=CRITICAL&status=OPEN")
    assert response.status_code == 200
    data = response.json()
    for item in data.get("items", []):
        assert item["severity"] == "CRITICAL"
        assert item["status"] == "OPEN"


# 4. Test ICMP Report API
def test_get_icmp_report_json():
    response = client.get("/api/v1/reports/icmp?time_range=7d")
    assert response.status_code == 200
    data = response.json()

    assert "total_checks" in data
    assert "avg_availability_pct" in data
    assert "items" in data


def test_get_icmp_report_csv_and_pdf():
    csv_resp = client.get("/api/v1/reports/icmp/csv?time_range=24h")
    assert csv_resp.status_code == 200
    assert "Device Name" in csv_resp.text

    pdf_resp = client.get("/api/v1/reports/icmp/pdf?time_range=24h")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF-")


# 5. Test TCP Report API
def test_get_tcp_report_json():
    response = client.get("/api/v1/reports/tcp?time_range=24h")
    assert response.status_code == 200
    data = response.json()

    assert "total_checks" in data
    assert "overall_availability_pct" in data
    assert "items" in data


def test_get_tcp_report_port_filter():
    response = client.get("/api/v1/reports/tcp?port=80")
    assert response.status_code == 200
    data = response.json()
    for item in data.get("items", []):
        assert item["port"] == 80


# 6. Test SNMP Report API
def test_get_snmp_report_json():
    response = client.get("/api/v1/reports/snmp?time_range=24h")
    assert response.status_code == 200
    data = response.json()

    assert "total_devices" in data
    assert "items" in data


def test_get_snmp_report_csv_and_pdf():
    csv_resp = client.get("/api/v1/reports/snmp/csv?time_range=24h")
    assert csv_resp.status_code == 200

    pdf_resp = client.get("/api/v1/reports/snmp/pdf?time_range=24h")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF-")


# 7. Custom Date Filtering Test
def test_report_custom_date_filtering():
    now = datetime.now(timezone.utc)
    st = (now - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    et = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    response = client.get(f"/api/v1/reports/network-health?time_range=custom&start_time={st}&end_time={et}")
    assert response.status_code == 200
    data = response.json()
    assert "Custom Range" in data["reporting_period"]


# 8. Empty / Non-existent Filter Testing
def test_report_non_existent_device_filter():
    dummy_uuid = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/reports/device-availability?device_id={dummy_uuid}")
    assert response.status_code == 200
    data = response.json()
    assert data["total_devices"] == 0
    assert len(data["items"]) == 0
