from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.core.security import verify_password, create_access_token, get_password_hash, generate_reset_token, hash_reset_token
from app.api.deps import get_current_user
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.schemas.user import (
    UserLogin, 
    TokenResponse, 
    UserResponse, 
    ForgotPasswordRequest, 
    ForgotPasswordResponse, 
    ResetPasswordRequest, 
    ResetPasswordResponse,
    SetupStatusResponse,
    InitialSetupRequest
)
from app.services.audit import log_audit_event
from app.services.email_service import send_password_reset_email

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    payload: UserLogin,
    db: Session = Depends(get_db)
):
    """Authenticate credentials and generate JWT token, recording audit log."""
    client_ip = request.client.host if request.client else None
    
    # Query by username or email
    user = db.query(User).filter(
        (User.email == payload.username_or_email) | (User.username == payload.username_or_email)
    ).first()
    
    if not user or not verify_password(payload.password, user.hashed_password):
        # Audit fail event
        log_audit_event(
            db=db,
            action="login_failure",
            details={"username_or_email": payload.username_or_email},
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    if not user.is_active:
        log_audit_event(
            db=db,
            action="login_failure_inactive",
            user=user,
            details={"username_or_email": payload.username_or_email},
            ip_address=client_ip
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )
        
    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)
    
    # Audit success event
    log_audit_event(
        db=db,
        action="login_success",
        user=user,
        ip_address=client_ip
    )
    
    access_token = create_access_token(
        subject=user.email,
        role=user.role
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user,
        "role": user.role
    }

@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Return profile info of the currently authenticated user."""
    return current_user

@router.post("/logout")
def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Log logout event. JWT is stateless; client must discard the token."""
    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="logout",
        user=current_user,
        ip_address=client_ip
    )
    return {"message": "Stateless logout successful. Please clear token from client storage."}

@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request a password reset link.
    Returns the exact same generic response whether email exists or not.
    """
    client_ip = request.client.host if request.client else None
    generic_msg = "If an account exists for this email, a password reset link has been sent."
    
    user = db.query(User).filter(User.email == payload.email).first()
    
    dev_url = None
    raw_token = None

    if user and user.is_active:
        now = datetime.now(timezone.utc)
        
        # Invalidate previous active reset tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used_at.is_(None)
        ).update({"used_at": now}, synchronize_session=False)
        
        # Generate new reset token & secure hash
        raw_token = generate_reset_token()
        token_hash = hash_reset_token(raw_token)
        expires_at = now + timedelta(minutes=settings.RESET_TOKEN_EXPIRE_MINUTES)
        
        reset_token_obj = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )
        db.add(reset_token_obj)
        db.commit()
        
        # Send reset email safely via EmailService
        try:
            dev_info = send_password_reset_email(email=user.email, reset_token=raw_token)
            dev_url = dev_info.get("reset_url")
        except Exception as email_err:
            pass  # Logged internally in EmailService, do not expose details to user API response
        
        # Log audit event (NEVER log raw token)
        log_audit_event(
            db=db,
            action="forgot_password_requested",
            user=user,
            details={"email": user.email},
            ip_address=client_ip
        )
    else:
        # Audit attempt for unknown/inactive email
        log_audit_event(
            db=db,
            action="forgot_password_attempt_unknown",
            details={"email": payload.email},
            ip_address=client_ip
        )

    # In development mode (when SMTP is not configured), expose dev helper fields for local debugging
    if settings.ENVIRONMENT == "development" and not settings.SMTP_HOST and dev_url:
        return ForgotPasswordResponse(
            message=generic_msg,
            dev_reset_url=dev_url,
            dev_token=raw_token,
            dev_note="[DEVELOPMENT ONLY] SMTP not configured. Reset link provided for development."
        )

    return ForgotPasswordResponse(message=generic_msg)

@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset user password using a valid, single-use reset token.
    """
    client_ip = request.client.host if request.client else None
    
    # 1. Password confirmation check if sent
    if payload.confirm_password is not None and payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match"
        )
        
    # 2. Password strength check
    if len(payload.new_password.strip()) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long"
        )

    # 3. Hash incoming token and query database
    incoming_hash = hash_reset_token(payload.token)
    reset_token_obj = db.query(PasswordResetToken).filter(
        PasswordResetToken.token_hash == incoming_hash
    ).first()
    
    if not reset_token_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
        
    # 4. Check if token already used
    if reset_token_obj.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )
        
    # 5. Check if token has expired
    now = datetime.now(timezone.utc)
    if reset_token_obj.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )

    # 6. Retrieve associated user
    user = db.query(User).filter(User.id == reset_token_obj.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token"
        )

    # 7. Update password and record password_changed_at for token revocation
    user.hashed_password = get_password_hash(payload.new_password)
    user.password_changed_at = now
    
    # 8. Mark token as used & invalidate any remaining tokens for this user
    reset_token_obj.used_at = now
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None)
    ).update({"used_at": now}, synchronize_session=False)

    db.commit()

    # 9. Audit event (NEVER log password or token)
    log_audit_event(
        db=db,
        action="password_reset_success",
        user=user,
        ip_address=client_ip
    )

    return ResetPasswordResponse(
        message="Password reset successful. You may now log in with your new password."
    )


@router.get("/setup-status", response_model=SetupStatusResponse)
def get_setup_status(db: Session = Depends(get_db)):
    """
    Detect whether the database contains an administrator account.
    Returns is_initialized = true if an administrator exists.
    """
    admin_exists = db.query(User).filter(User.role == "ADMIN").first() is not None
    return SetupStatusResponse(is_initialized=admin_exists)


@router.post("/setup-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def setup_initial_admin(
    request: Request,
    payload: InitialSetupRequest,
    db: Session = Depends(get_db)
):
    """
    Perform first-time setup for the initial administrator.
    Protected against race conditions and disallowed once an admin exists.
    """
    # 1. Password confirmation check if provided
    if payload.confirm_password is not None and payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match. Please verify and try again."
        )

    # 2. Race-condition protection & initialization check
    # Execute query to check existing admin count
    admin_count = db.query(User).filter(User.role == "ADMIN").count()
    if admin_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="System is already initialized. First-time setup is no longer available."
        )

    # 3. Email uniqueness check
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email address is already registered."
        )

    # 4. Username handling & uniqueness check
    username = payload.username
    if not username:
        username = payload.email.split("@")[0]

    if db.query(User).filter(User.username == username).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already taken."
        )

    # 5. Create initial administrator
    hashed = get_password_hash(payload.password)
    admin_user = User(
        email=payload.email,
        username=username,
        hashed_password=hashed,
        full_name=payload.full_name,
        role="ADMIN",
        is_active=True
    )
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)

    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="initial_setup_completed",
        user=admin_user,
        details={"admin_email": admin_user.email, "username": admin_user.username},
        ip_address=client_ip
    )

    return admin_user


