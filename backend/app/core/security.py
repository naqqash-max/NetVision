import bcrypt
import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Union
from jose import jwt
from app.core.config import settings

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    """Generate a bcrypt hash of the given password."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")

def generate_reset_token() -> str:
    """Generate a cryptographically secure, random single-use token string."""
    return secrets.token_urlsafe(32)

def hash_reset_token(token: str) -> str:
    """Compute SHA-256 hash of a reset token for secure DB storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_access_token(subject: Union[str, Any], role: str, expires_delta: timedelta = None) -> str:
    """Create a signed JWT access token containing subject, role, and issued-at timestamp."""
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "iat": int(now.timestamp()),
        "sub": str(subject),
        "role": role
    }
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

