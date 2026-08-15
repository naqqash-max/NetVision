from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_password_hash
from app.api.deps import require_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse
from app.services.audit import log_audit_event

router = APIRouter()

@router.get("", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Retrieve all users in the system (ADMIN only)."""
    return db.query(User).all()

@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    request: Request,
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Register a new user (ADMIN only)."""
    # Check if email exists
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Check if username exists
    if payload.username and db.query(User).filter(User.username == payload.username).first():
        raise HTTPException(status_code=400, detail="Username already taken")
        
    hashed = get_password_hash(payload.password)
    new_user = User(
        email=payload.email,
        username=payload.username,
        hashed_password=hashed,
        full_name=payload.full_name,
        role=payload.role,
        is_active=payload.is_active
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Log audit event
    client_ip = request.client.host if request.client else None
    log_audit_event(
        db=db,
        action="user_creation",
        user=current_user,
        details={"created_user_id": str(new_user.id), "username": new_user.username, "role": new_user.role},
        ip_address=client_ip
    )
    
    return new_user

@router.get("/{id}", response_model=UserResponse)
def get_user(
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get a user by ID (ADMIN only)."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/{id}", response_model=UserResponse)
def update_user(
    request: Request,
    id: UUID,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Modify user information, including role and active state (ADMIN only)."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    client_ip = request.client.host if request.client else None
    
    # Safeguard check: If updating active state or role of an administrator
    if user.role == "ADMIN":
        # Check if the update will deactivate the user or change their role from ADMIN
        will_deactivate = payload.is_active is False
        will_demote = payload.role is not None and payload.role != "ADMIN"
        
        if will_deactivate or will_demote:
            # Count remaining active administrators
            active_admins_count = db.query(User).filter(User.role == "ADMIN", User.is_active == True).count()
            if active_admins_count <= 1:
                raise HTTPException(
                    status_code=400, 
                    detail="Cannot deactivate or demote the last active administrator."
                )

    if payload.email and payload.email != user.email:
        if db.query(User).filter(User.email == payload.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        user.email = payload.email
        
    if payload.username and payload.username != user.username:
        if db.query(User).filter(User.username == payload.username).first():
            raise HTTPException(status_code=400, detail="Username already taken")
        user.username = payload.username
        
    if payload.password:
        user.hashed_password = get_password_hash(payload.password)
        
    if payload.full_name is not None:
        user.full_name = payload.full_name
        
    role_changed = False
    old_role = user.role
    if payload.role is not None and payload.role != user.role:
        user.role = payload.role
        role_changed = True
        
    status_changed = False
    old_status = user.is_active
    if payload.is_active is not None and payload.is_active != user.is_active:
        user.is_active = payload.is_active
        status_changed = True
        
    db.commit()
    db.refresh(user)
    
    # Audit logging
    if role_changed:
        log_audit_event(
            db=db,
            action="role_changes",
            user=current_user,
            details={"target_user_id": str(user.id), "old_role": old_role, "new_role": user.role},
            ip_address=client_ip
        )
    if status_changed:
        action_name = "user_deactivation" if not user.is_active else "user_reactivation"
        log_audit_event(
            db=db,
            action=action_name,
            user=current_user,
            details={"target_user_id": str(user.id)},
            ip_address=client_ip
        )
        
    log_audit_event(
        db=db,
        action="user_update",
        user=current_user,
        details={"updated_user_id": str(user.id)},
        ip_address=client_ip
    )
    
    return user

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    request: Request,
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Delete a user from the system (ADMIN only)."""
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    client_ip = request.client.host if request.client else None
    
    # Safeguard check: If deleting an administrator
    if user.role == "ADMIN":
        active_admins_count = db.query(User).filter(User.role == "ADMIN", User.is_active == True).count()
        if active_admins_count <= 1:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete the last active administrator."
            )
            
    db.delete(user)
    db.commit()
    
    log_audit_event(
        db=db,
        action="user_deletion",
        user=current_user,
        details={"deleted_user_id": str(id), "username": user.username or user.email},
        ip_address=client_ip
    )
    return None

@router.post("/{id}/send-password-reset")
def admin_send_password_reset(
    request: Request,
    id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Initiate a password reset for a user without seeing or knowing their password (ADMIN only)."""
    from datetime import datetime, timezone, timedelta
    from app.core.config import settings
    from app.core.security import generate_reset_token, hash_reset_token
    from app.models.password_reset import PasswordResetToken
    from app.services.email import send_password_reset_email

    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    client_ip = request.client.host if request.client else None
    now = datetime.now(timezone.utc)
    
    # Invalidate previous unused reset tokens for target user
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None)
    ).update({"used_at": now}, synchronize_session=False)

    # Generate token & hash
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

    dev_info = send_password_reset_email(email=user.email, reset_token=raw_token)
    dev_url = dev_info["reset_url"]

    # Audit log event
    log_audit_event(
        db=db,
        action="admin_password_reset_initiated",
        user=current_user,
        details={"target_user_id": str(user.id), "target_email": user.email},
        ip_address=client_ip
    )

    response_data = {
        "message": f"Password reset link successfully sent to {user.email}."
    }
    if settings.ENVIRONMENT == "development" and not settings.SMTP_HOST and dev_url:
        response_data["dev_reset_url"] = dev_url
        response_data["dev_token"] = raw_token
        response_data["dev_note"] = "[DEVELOPMENT ONLY] SMTP not configured. Reset link provided for development."

    return response_data

