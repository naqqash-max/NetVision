import time
import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.core.db import SessionLocal
from app.core.security import hash_reset_token, verify_password
from app.models.user import User
from app.models.password_reset import PasswordResetToken

client = TestClient(app)

@pytest.fixture(autouse=True)
def dev_mode_no_smtp(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "SMTP_HOST", "")

@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        # Cleanup test password recovery users & tokens
        test_users = db.query(User).filter(User.email.like("recovery_%@netvision.com")).all()
        for u in test_users:
            db.delete(u)
        db.commit()
        db.close()

def test_forgot_password_generic_response_and_token_creation(db_session):
    # Create test user for password recovery
    user_email = "recovery_test1@netvision.com"
    db_session.query(User).filter(User.email == user_email).delete()
    db_session.commit()

    test_user = User(
        email=user_email,
        username="recuser1",
        hashed_password="oldhashedpassword123",
        role="OPERATOR",
        is_active=True
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    # 1. Valid forgot-password request
    resp_valid = client.post("/api/v1/auth/forgot-password", json={"email": user_email})
    assert resp_valid.status_code == 200
    valid_data = resp_valid.json()
    assert valid_data["message"] == "If an account exists for this email, a password reset link has been sent."

    # Verify token hash was created in DB and raw token is NOT stored
    token_record = db_session.query(PasswordResetToken).filter(PasswordResetToken.user_id == test_user.id).order_by(PasswordResetToken.created_at.desc()).first()
    assert token_record is not None
    assert token_record.used_at is None
    
    # In dev mode response or dev log, we can get raw_token to verify hash
    dev_token = valid_data.get("dev_token")
    if dev_token:
        assert token_record.token_hash == hash_reset_token(dev_token)
        assert dev_token != token_record.token_hash

    # 2. Unknown email request
    unknown_email = "recovery_unknown999@netvision.com"
    resp_unknown = client.post("/api/v1/auth/forgot-password", json={"email": unknown_email})
    assert resp_unknown.status_code == 200
    unknown_data = resp_unknown.json()
    
    # Requirement: Identical generic response for known and unknown emails
    assert unknown_data["message"] == valid_data["message"]

from app.services import email_service

def test_previous_reset_token_invalidation(db_session):
    user_email = "recovery_test2@netvision.com"
    db_session.query(User).filter(User.email == user_email).delete()
    db_session.commit()

    test_user = User(
        email=user_email,
        username="recuser2",
        hashed_password="oldhashedpassword123",
        role="VIEWER",
        is_active=True
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    # First request
    resp1 = client.post("/api/v1/auth/forgot-password", json={"email": user_email})
    token1 = resp1.json().get("dev_token") or (email_service.latest_dev_email and email_service.latest_dev_email.get("token"))
    
    # Second request for same user
    resp2 = client.post("/api/v1/auth/forgot-password", json={"email": user_email})
    token2 = resp2.json().get("dev_token") or (email_service.latest_dev_email and email_service.latest_dev_email.get("token"))

    assert token1 != token2

    # First token should be invalidated/used
    resp_reset1 = client.post("/api/v1/auth/reset-password", json={
        "token": token1,
        "new_password": "newpassword123"
    })
    assert resp_reset1.status_code == 400
    assert "Invalid or expired password reset token" in resp_reset1.json()["detail"]

    # Second token should work
    resp_reset2 = client.post("/api/v1/auth/reset-password", json={
        "token": token2,
        "new_password": "newpassword123"
    })
    assert resp_reset2.status_code == 200
    assert "Password reset successful" in resp_reset2.json()["message"]

def test_reset_token_expiration(db_session):
    user_email = "recovery_test3@netvision.com"
    db_session.query(User).filter(User.email == user_email).delete()
    db_session.commit()

    test_user = User(
        email=user_email,
        username="recuser3",
        hashed_password="oldhashedpassword123",
        role="OPERATOR",
        is_active=True
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    # Manually create an expired token record in DB
    raw_token = "expired_test_token_12345"
    token_hash = hash_reset_token(raw_token)
    expired_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    expired_record = PasswordResetToken(
        user_id=test_user.id,
        token_hash=token_hash,
        expires_at=expired_time
    )
    db_session.add(expired_record)
    db_session.commit()

    resp = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "newpassword123"
    })
    assert resp.status_code == 400
    assert "Invalid or expired password reset token" in resp.json()["detail"]

def test_invalid_and_reused_token(db_session):
    # Invalid random token
    resp = client.post("/api/v1/auth/reset-password", json={
        "token": "completely_fake_invalid_token",
        "new_password": "newpassword123"
    })
    assert resp.status_code == 400

    # Test single-use (reused token)
    user_email = "recovery_test4@netvision.com"
    db_session.query(User).filter(User.email == user_email).delete()
    db_session.commit()

    test_user = User(
        email=user_email,
        username="recuser4",
        hashed_password="oldpassword123",
        role="OPERATOR",
        is_active=True
    )
    db_session.add(test_user)
    db_session.commit()

    resp_forgot = client.post("/api/v1/auth/forgot-password", json={"email": user_email})
    token = resp_forgot.json().get("dev_token") or (email_service.latest_dev_email and email_service.latest_dev_email.get("token"))

    # Use token once
    reset_resp1 = client.post("/api/v1/auth/reset-password", json={
        "token": token,
        "new_password": "newpassword123"
    })
    assert reset_resp1.status_code == 200

    # Try to reuse token
    reset_resp2 = client.post("/api/v1/auth/reset-password", json={
        "token": token,
        "new_password": "anotherpassword123"
    })
    assert reset_resp2.status_code == 400
    assert "Invalid or expired password reset token" in reset_resp2.json()["detail"]

def test_password_validation_and_mismatch():
    # Weak password (< 6 chars)
    resp_weak = client.post("/api/v1/auth/reset-password", json={
        "token": "some_token",
        "new_password": "123"
    })
    assert resp_weak.status_code == 422 or resp_weak.status_code == 400

    # Password mismatch
    resp_mismatch = client.post("/api/v1/auth/reset-password", json={
        "token": "some_token",
        "new_password": "validpassword123",
        "confirm_password": "differentpassword123"
    })
    assert resp_mismatch.status_code == 400
    assert "Passwords do not match" in resp_mismatch.json()["detail"]

def test_full_reset_and_login_flow(db_session):
    user_email = "recovery_full_flow@netvision.com"
    db_session.query(User).filter(User.email == user_email).delete()
    db_session.commit()

    old_password = "initialPassword123!"
    new_password = "updatedSecurePassword456!"

    # 1. Create user
    from app.core.security import get_password_hash
    test_user = User(
        email=user_email,
        username="fullflowuser",
        hashed_password=get_password_hash(old_password),
        role="OPERATOR",
        is_active=True
    )
    db_session.add(test_user)
    db_session.commit()
    db_session.refresh(test_user)

    old_hash = test_user.hashed_password

    # 2. Login with old password works initially
    login_old = client.post("/api/v1/auth/login", json={
        "username_or_email": user_email,
        "password": old_password
    })
    assert login_old.status_code == 200
    old_jwt_token = login_old.json()["access_token"]

    # 3. Request password reset (sleep 1.1s to ensure distinct second timestamp for token revocation check)
    time.sleep(1.1)
    forgot_resp = client.post("/api/v1/auth/forgot-password", json={"email": user_email})
    assert forgot_resp.status_code == 200

    reset_token = forgot_resp.json().get("dev_token") or (email_service.latest_dev_email and email_service.latest_dev_email.get("token"))

    # 4. Perform password reset
    reset_resp = client.post("/api/v1/auth/reset-password", json={
        "token": reset_token,
        "new_password": new_password,
        "confirm_password": new_password
    })
    assert reset_resp.status_code == 200

    # 5. Verify database password hash changed
    db_session.refresh(test_user)
    assert test_user.hashed_password != old_hash
    assert verify_password(new_password, test_user.hashed_password) is True

    # 6. Verify RBAC role retained
    assert test_user.role == "OPERATOR"

    # 7. Old password no longer works
    login_old_after = client.post("/api/v1/auth/login", json={
        "username_or_email": user_email,
        "password": old_password
    })
    assert login_old_after.status_code == 401

    # 8. New password works
    login_new = client.post("/api/v1/auth/login", json={
        "username_or_email": user_email,
        "password": new_password
    })
    assert login_new.status_code == 200
    assert login_new.json()["role"] == "OPERATOR"

    # 9. Session Token Revocation: Pre-reset JWT should now fail when used for authenticated requests
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {old_jwt_token}"})
    assert me_resp.status_code == 401

def test_admin_initiated_password_reset(db_session):
    # Admin login
    admin_login = client.post("/api/v1/auth/login", json={
        "username_or_email": "admin",
        "password": "admin123"
    })
    assert admin_login.status_code == 200
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Create target user
    user_email = "recovery_admin_target@netvision.com"
    db_session.query(User).filter(User.email == user_email).delete()
    db_session.commit()

    from app.core.security import get_password_hash
    target_user = User(
        email=user_email,
        username="admintarget",
        hashed_password=get_password_hash("secretuserpass123"),
        role="VIEWER",
        is_active=True
    )
    db_session.add(target_user)
    db_session.commit()
    db_session.refresh(target_user)

    # Admin calls send-password-reset endpoint
    resp = client.post(f"/api/v1/users/{target_user.id}/send-password-reset", headers=admin_headers)
    assert resp.status_code == 200
    json_data = resp.json()
    assert "Password reset link successfully sent" in json_data["message"]
    
    # Verify admin response does NOT reveal user's password or hash
    assert "hashed_password" not in json_data
    assert "password" not in json_data

    # Verify reset token was generated for target user
    dev_token = json_data.get("dev_token") or (email_service.latest_dev_email and email_service.latest_dev_email.get("token"))
    assert dev_token is not None

    # Use the generated token to set new password
    reset_resp = client.post("/api/v1/auth/reset-password", json={
        "token": dev_token,
        "new_password": "adminSetNewPass789!"
    })
    assert reset_resp.status_code == 200

    # User logs in with new password
    user_login = client.post("/api/v1/auth/login", json={
        "username_or_email": user_email,
        "password": "adminSetNewPass789!"
    })
    assert user_login.status_code == 200

def test_smtp_failure_handling(db_session, monkeypatch):
    """Verify API handles SMTP connection errors safely without leaking credentials or throwing 500."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "SMTP_HOST", "mailpit")

    user_email = "recovery_smtp_fail@netvision.com"
    db_session.query(User).filter(User.email == user_email).delete()
    db_session.commit()

    from app.core.security import get_password_hash
    test_user = User(
        email=user_email,
        username="smtpfailuser",
        hashed_password=get_password_hash("password123"),
        role="VIEWER",
        is_active=True
    )
    db_session.add(test_user)
    db_session.commit()

    # Simulate an SMTP network exception
    def mock_smtp_fail(*args, **kwargs):
        raise ConnectionRefusedError("Simulated SMTP Connection Failure")

    import smtplib
    monkeypatch.setattr(smtplib, "SMTP", mock_smtp_fail)

    resp = client.post("/api/v1/auth/forgot-password", json={"email": user_email})
    assert resp.status_code == 200
    data = resp.json()
    # Must return generic message without exposing internal exception details or credentials
    assert data["message"] == "If an account exists for this email, a password reset link has been sent."
    assert "Simulated SMTP" not in str(data)

def test_disabled_email_service(db_session, monkeypatch):
    """Verify email service behavior when EMAIL_ENABLED is set to False."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "EMAIL_ENABLED", False)

    from app.services.email_service import EmailService
    result = EmailService.send_password_reset("disabled_test@netvision.com", "dummytoken123")
    assert result["success"] is True
    assert result["email"] == "disabled_test@netvision.com"

