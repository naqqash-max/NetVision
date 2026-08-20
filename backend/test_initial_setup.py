import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.db import SessionLocal
from app.models.user import User

client = TestClient(app)

@pytest.fixture
def clean_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        test_users = db.query(User).filter(
            (User.email.like("test_setup_%")) | 
            (User.email.like("setup_admin_%")) |
            (User.email.like("%_test@netvision.com")) |
            (User.email == "newadmin@netvision.com") |
            (User.email == "should_fail@netvision.com")
        ).all()
        for u in test_users:
            db.delete(u)
        db.commit()
        db.close()

def test_setup_status_endpoint(clean_db):
    """Verify /api/v1/auth/setup-status endpoint returns boolean is_initialized."""
    response = client.get("/api/v1/auth/setup-status")
    assert response.status_code == 200
    data = response.json()
    assert "is_initialized" in data
    assert isinstance(data["is_initialized"], bool)

def test_setup_invalid_email_fails():
    """Verify setup fails with 422 for invalid email address."""
    response = client.post("/api/v1/auth/setup-admin", json={
        "email": "not-an-email",
        "full_name": "Invalid Email Admin",
        "password": "strongpassword123",
        "confirm_password": "strongpassword123"
    })
    assert response.status_code == 422

def test_setup_weak_password_fails():
    """Verify setup fails when password is less than 6 characters."""
    response = client.post("/api/v1/auth/setup-admin", json={
        "email": "test_setup_weak@netvision.com",
        "full_name": "Weak Pass Admin",
        "password": "123",
        "confirm_password": "123"
    })
    assert response.status_code == 422

def test_setup_password_mismatch_fails(clean_db):
    """Verify setup fails when password and confirm_password do not match."""
    response = client.post("/api/v1/auth/setup-admin", json={
        "email": "test_setup_mismatch@netvision.com",
        "full_name": "Mismatch Pass Admin",
        "password": "password123",
        "confirm_password": "differentpassword123"
    })
    assert response.status_code == 400
    assert "Passwords do not match" in response.json()["detail"]

def test_duplicate_initialization_blocked_when_admin_exists(clean_db):
    """Verify setup fails when an administrator already exists in the system."""
    status_res = client.get("/api/v1/auth/setup-status")
    assert status_res.json()["is_initialized"] is True

    response = client.post("/api/v1/auth/setup-admin", json={
        "email": "test_setup_duplicate@netvision.com",
        "full_name": "Duplicate Admin",
        "password": "password123",
        "confirm_password": "password123"
    })
    assert response.status_code == 400
    assert "System is already initialized" in response.json()["detail"]

def test_user_creation_by_admin_and_non_admin_blocking(clean_db):
    """Verify ADMIN can create new users (ADMIN, OPERATOR, VIEWER) and non-admin is blocked."""
    # 1. Obtain admin access token
    admin_login = client.post("/api/v1/auth/login", json={
        "username_or_email": "admin@netvision.com",
        "password": "admin123"
    })
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 2. Admin creates a VIEWER user
    create_viewer_res = client.post("/api/v1/users", json={
        "email": "viewer_test@netvision.com",
        "username": "viewer_setup",
        "password": "viewerpassword123",
        "full_name": "Test Setup Viewer",
        "role": "VIEWER",
        "is_active": True
    }, headers=admin_headers)
    assert create_viewer_res.status_code == 201
    viewer_data = create_viewer_res.json()
    assert viewer_data["role"] == "VIEWER"

    # 3. Admin creates an OPERATOR user
    create_op_res = client.post("/api/v1/users", json={
        "email": "operator_test@netvision.com",
        "username": "op_setup",
        "password": "operatorpassword123",
        "full_name": "Test Setup Operator",
        "role": "OPERATOR",
        "is_active": True
    }, headers=admin_headers)
    assert create_op_res.status_code == 201
    assert create_op_res.json()["role"] == "OPERATOR"

    # 4. Login as non-admin VIEWER
    viewer_login = client.post("/api/v1/auth/login", json={
        "username_or_email": "viewer_test@netvision.com",
        "password": "viewerpassword123"
    })
    assert viewer_login.status_code == 200
    viewer_token = viewer_login.json()["access_token"]
    viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

    # 5. Non-admin VIEWER attempting user creation must be blocked with HTTP 403 Forbidden
    blocked_res = client.post("/api/v1/users", json={
        "email": "should_fail@netvision.com",
        "password": "password123",
        "role": "OPERATOR"
    }, headers=viewer_headers)
    assert blocked_res.status_code == 403

def test_first_admin_creation_flow(clean_db):
    """
    Test first-time administrator setup in an isolated environment.
    Temporarily removes existing admins, runs setup-admin, verifies success, and restores DB.
    """
    db = SessionLocal()
    temp_saved_users = []
    try:
        # Temporarily delete existing users to simulate empty DB
        existing_users = db.query(User).all()
        for u in existing_users:
            temp_saved_users.append({
                "email": u.email,
                "username": u.username,
                "hashed_password": u.hashed_password,
                "full_name": u.full_name,
                "role": u.role,
                "is_active": u.is_active
            })
            db.delete(u)
        db.commit()

        # Verify system setup status is False when no admin exists
        status_res = client.get("/api/v1/auth/setup-status")
        assert status_res.status_code == 200
        assert status_res.json()["is_initialized"] is False

        # Run first admin setup
        setup_res = client.post("/api/v1/auth/setup-admin", json={
            "email": "newadmin@netvision.com",
            "full_name": "First Initial Admin",
            "username": "first_admin",
            "password": "adminpassword123",
            "confirm_password": "adminpassword123"
        })
        assert setup_res.status_code == 201
        created = setup_res.json()
        assert created["role"] == "ADMIN"
        assert created["email"] == "newadmin@netvision.com"

        # Verify system setup status is now True
        status_res_after = client.get("/api/v1/auth/setup-status")
        assert status_res_after.json()["is_initialized"] is True

        # Verify newly created admin can log in
        login_res = client.post("/api/v1/auth/login", json={
            "username_or_email": "newadmin@netvision.com",
            "password": "adminpassword123"
        })
        assert login_res.status_code == 200
        assert login_res.json()["role"] == "ADMIN"

    finally:
        # Restore saved users
        db.query(User).delete()
        db.commit()
        for user_dict in temp_saved_users:
            db.add(User(**user_dict))
        db.commit()
        db.close()
