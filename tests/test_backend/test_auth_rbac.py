import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal
from app.models.user import User
from app.models.audit_log import AuditLog

client = TestClient(app)

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        # Clean up any test users created during tests
        test_users = db.query(User).filter(User.email.like("test_%@netvision.com")).all()
        for u in test_users:
            db.delete(u)
        db.commit()
        db.close()

def test_login_success():
    # Login with email
    response = client.post("/api/v1/auth/login", json={
        "username_or_email": "admin@netvision.local",
        "password": "admin123"
    })
    assert response.status_code == 200
    json_data = response.json()
    assert "access_token" in json_data
    assert json_data["token_type"] == "bearer"
    assert json_data["role"] == "ADMIN"
    assert json_data["user"]["email"] == "admin@netvision.local"
    assert "hashed_password" not in json_data["user"]

    # Login with username
    response2 = client.post("/api/v1/auth/login", json={
        "username_or_email": "admin",
        "password": "admin123"
    })
    assert response2.status_code == 200

def test_login_invalid_credentials():
    # Wrong password
    response = client.post("/api/v1/auth/login", json={
        "username_or_email": "admin@netvision.local",
        "password": "wrongpassword"
    })
    assert response.status_code == 401
    
    # Non-existent user
    response = client.post("/api/v1/auth/login", json={
        "username_or_email": "fakeuser@netvision.local",
        "password": "admin123"
    })
    assert response.status_code == 401

def test_me_endpoint_requires_auth():
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401

def test_me_endpoint_success():
    # Login to get token
    login_resp = client.post("/api/v1/auth/login", json={
        "username_or_email": "admin",
        "password": "admin123"
    })
    token = login_resp.json()["access_token"]
    
    # Call /me
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "admin@netvision.local"

def test_logout_endpoint():
    login_resp = client.post("/api/v1/auth/login", json={
        "username_or_email": "admin",
        "password": "admin123"
    })
    token = login_resp.json()["access_token"]
    
    response = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert "Stateless logout successful" in response.json()["message"]

def test_user_management_rbac(db_session):
    # 1. Login as Admin
    admin_login = client.post("/api/v1/auth/login", json={
        "username_or_email": "admin",
        "password": "admin123"
    })
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # 2. Create target roles
    # Create ADMIN
    resp = client.post("/api/v1/users", headers=admin_headers, json={
        "email": "test_admin@netvision.com",
        "username": "testadmin",
        "password": "testpassword123",
        "full_name": "Test Admin",
        "role": "ADMIN",
        "is_active": True
    })
    assert resp.status_code == 201
    
    # Create OPERATOR
    resp = client.post("/api/v1/users", headers=admin_headers, json={
        "email": "test_operator@netvision.com",
        "username": "testoperator",
        "password": "testpassword123",
        "full_name": "Test Operator",
        "role": "OPERATOR",
        "is_active": True
    })
    assert resp.status_code == 201
    
    # Create VIEWER
    resp = client.post("/api/v1/users", headers=admin_headers, json={
        "email": "test_viewer@netvision.com",
        "username": "testviewer",
        "password": "testpassword123",
        "full_name": "Test Viewer",
        "role": "VIEWER",
        "is_active": True
    })
    assert resp.status_code == 201

    # Create Inactive User
    resp = client.post("/api/v1/users", headers=admin_headers, json={
        "email": "test_inactive@netvision.com",
        "username": "testinactive",
        "password": "testpassword123",
        "full_name": "Test Inactive",
        "role": "VIEWER",
        "is_active": False
    })
    assert resp.status_code == 201
    
    # 3. Verify Inactive user cannot login
    resp = client.post("/api/v1/auth/login", json={
        "username_or_email": "testinactive",
        "password": "testpassword123"
    })
    assert resp.status_code == 400 or resp.status_code == 401

    # 4. Get Tokens for all roles
    operator_token = client.post("/api/v1/auth/login", json={
        "username_or_email": "testoperator",
        "password": "testpassword123"
    }).json()["access_token"]
    operator_headers = {"Authorization": f"Bearer {operator_token}"}
    
    viewer_token = client.post("/api/v1/auth/login", json={
        "username_or_email": "testviewer",
        "password": "testpassword123"
    }).json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # 5. Verify User Management endpoints are ADMIN-only
    # VIEWER and OPERATOR must get 403 Forbidden
    assert client.get("/api/v1/users", headers=viewer_headers).status_code == 403
    assert client.get("/api/v1/users", headers=operator_headers).status_code == 403
    assert client.post("/api/v1/users", headers=viewer_headers, json={}).status_code == 403
    assert client.post("/api/v1/users", headers=operator_headers, json={}).status_code == 403
    
    # ADMIN must get 200
    assert client.get("/api/v1/users", headers=admin_headers).status_code == 200

def test_rbac_device_permissions():
    # Login roles
    admin_token = client.post("/api/v1/auth/login", json={"username_or_email": "admin", "password": "admin123"}).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    operator_token = client.post("/api/v1/auth/login", json={"username_or_email": "testoperator", "password": "testpassword123"}).json()["access_token"]
    operator_headers = {"Authorization": f"Bearer {operator_token}"}
    
    viewer_token = client.post("/api/v1/auth/login", json={"username_or_email": "testviewer", "password": "testpassword123"}).json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    
    # A. GET Devices
    assert client.get("/api/v1/devices/", headers=viewer_headers).status_code == 200
    assert client.get("/api/v1/devices/", headers=operator_headers).status_code == 200
    assert client.get("/api/v1/devices/", headers=admin_headers).status_code == 200
    
    # B. POST Device (ADMIN only)
    device_payload = {
        "ip_address": "192.168.10.99",
        "hostname": "test-device-rbac",
        "name": "RBAC Test Device",
        "device_type": "server",
        "monitoring_enabled": False,
        "ping_interval": 30
    }
    assert client.post("/api/v1/devices/", headers=viewer_headers, json=device_payload).status_code == 403
    assert client.post("/api/v1/devices/", headers=operator_headers, json=device_payload).status_code == 403
    
    create_resp = client.post("/api/v1/devices/", headers=admin_headers, json=device_payload)
    assert create_resp.status_code == 201
    device_id = create_resp.json()["id"]
    
    # C. Manual Monitoring (ADMIN & OPERATOR allowed, VIEWER denied)
    assert client.post(f"/api/v1/devices/{device_id}/monitor", headers=viewer_headers).status_code == 403
    assert client.post(f"/api/v1/devices/{device_id}/monitor", headers=operator_headers).status_code == 200
    assert client.post(f"/api/v1/devices/{device_id}/monitor", headers=admin_headers).status_code == 200
    
    # D. PUT Device (ADMIN only)
    update_payload = {"name": "Updated Name"}
    assert client.put(f"/api/v1/devices/{device_id}", headers=viewer_headers, json=update_payload).status_code == 403
    assert client.put(f"/api/v1/devices/{device_id}", headers=operator_headers, json=update_payload).status_code == 403
    assert client.put(f"/api/v1/devices/{device_id}", headers=admin_headers, json=update_payload).status_code == 200
    
    # E. DELETE Device (ADMIN only)
    assert client.delete(f"/api/v1/devices/{device_id}", headers=viewer_headers).status_code == 403
    assert client.delete(f"/api/v1/devices/{device_id}", headers=operator_headers).status_code == 403
    assert client.delete(f"/api/v1/devices/{device_id}", headers=admin_headers).status_code == 204

def test_rbac_alert_permissions():
    admin_token = client.post("/api/v1/auth/login", json={"username_or_email": "admin", "password": "admin123"}).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    operator_token = client.post("/api/v1/auth/login", json={"username_or_email": "testoperator", "password": "testpassword123"}).json()["access_token"]
    operator_headers = {"Authorization": f"Bearer {operator_token}"}
    
    viewer_token = client.post("/api/v1/auth/login", json={"username_or_email": "testviewer", "password": "testpassword123"}).json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
    
    # A. GET alerts
    assert client.get("/api/v1/alerts/", headers=viewer_headers).status_code == 200
    assert client.get("/api/v1/alerts/", headers=operator_headers).status_code == 200
    assert client.get("/api/v1/alerts/", headers=admin_headers).status_code == 200
    
    # B. PUT settings (ADMIN only)
    settings_payload = {"icmp_latency_warning": 250.0}
    assert client.put("/api/v1/alerts/settings", headers=viewer_headers, json=settings_payload).status_code == 403
    assert client.put("/api/v1/alerts/settings", headers=operator_headers, json=settings_payload).status_code == 403
    assert client.put("/api/v1/alerts/settings", headers=admin_headers, json=settings_payload).status_code == 200

def test_admin_safeguards():
    # Login as admin
    admin_token = client.post("/api/v1/auth/login", json={"username_or_email": "admin", "password": "admin123"}).json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    
    # Get test_admin details
    test_admin_resp = client.get("/api/v1/users", headers=admin_headers).json()
    test_admin_id = None
    default_admin_id = None
    for u in test_admin_resp:
        if u["email"] == "test_admin@netvision.com":
            test_admin_id = u["id"]
        elif u["email"] == "admin@netvision.local":
            default_admin_id = u["id"]
            
    # Attempt to deactivate test_admin (should succeed since default admin is still active admin)
    resp = client.put(f"/api/v1/users/{test_admin_id}", headers=admin_headers, json={"is_active": False})
    assert resp.status_code == 200
    
    # Attempt to deactivate default admin (should fail because it's the LAST active administrator)
    resp = client.put(f"/api/v1/users/{default_admin_id}", headers=admin_headers, json={"is_active": False})
    assert resp.status_code == 400
    assert "Cannot deactivate" in resp.json()["detail"]
    
    # Attempt to change role of default admin to VIEWER (should fail because it's the LAST active administrator)
    resp = client.put(f"/api/v1/users/{default_admin_id}", headers=admin_headers, json={"role": "VIEWER"})
    assert resp.status_code == 400
    assert "Cannot deactivate or demote" in resp.json()["detail"]
    
    # Attempt to delete default admin (should fail)
    resp = client.delete(f"/api/v1/users/{default_admin_id}", headers=admin_headers)
    assert resp.status_code == 400
    assert "Cannot delete" in resp.json()["detail"]
    
    # Reactivate test_admin
    resp = client.put(f"/api/v1/users/{test_admin_id}", headers=admin_headers, json={"is_active": True})
    assert resp.status_code == 200

def test_audit_logging(db_session):
    # Verify audit logs are created for actions
    logs = db_session.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(10).all()
    actions = [l.action for l in logs]
    
    # Check that key actions are present
    assert any(a in actions for a in ["login_success", "device_creation", "manual_monitoring", "alert_threshold_changes"])
    
    # Verify no passwords or secrets are recorded
    for l in logs:
        if l.details:
            assert "password" not in l.details.lower() or "********" in l.details.lower()
            assert "community" not in l.details.lower() or "********" in l.details.lower()
