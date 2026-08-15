from datetime import datetime, timezone, timedelta
from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_db
from app.models.user import User

# OAuth2 scheme config
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> User:
    """Retrieve the currently authenticated user based on JWT verification."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        username_or_email: str = payload.get("sub")
        if username_or_email is None:
            raise credentials_exception
        iat: int = payload.get("iat")
    except JWTError:
        raise credentials_exception
        
    user = db.query(User).filter(
        (User.email == username_or_email) | (User.username == username_or_email)
    ).first()
    
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Inactive user"
        )

    # Token Revocation Check: If password was changed after this token was issued
    if iat and user.password_changed_at:
        token_issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
        if token_issued_at < user.password_changed_at:
            raise credentials_exception


    return user


class RoleChecker:
    """Enforce specific roles on a FastAPI endpoint."""
    def __init__(self, allowed_roles: List[str]):
        self.allowed_roles = allowed_roles

    def __call__(self, current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user does not have enough privileges"
            )
        return current_user

# Pre-defined dependencies for endpoint protection
require_admin = RoleChecker(["ADMIN"])
require_operator = RoleChecker(["ADMIN", "OPERATOR"])
require_viewer = RoleChecker(["ADMIN", "OPERATOR", "VIEWER"])
