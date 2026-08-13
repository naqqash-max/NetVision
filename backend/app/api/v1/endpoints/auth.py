from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import verify_password, create_access_token
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.user import UserLogin, TokenResponse, UserResponse
from app.services.audit import log_audit_event

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
    user.last_login = datetime.utcnow()
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
