from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict

class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = None
    role: str = "VIEWER"
    is_active: bool = True

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ["ADMIN", "OPERATOR", "VIEWER"]:
            raise ValueError("Role must be one of: ADMIN, OPERATOR, VIEWER")
        return v

class UserCreate(UserBase):
    password: Optional[str] = Field(None, min_length=6, description="Password must be at least 6 characters long")
    send_invite: bool = False

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=6)
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator('role')
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ["ADMIN", "OPERATOR", "VIEWER"]:
            raise ValueError("Role must be one of: ADMIN, OPERATOR, VIEWER")
        return v

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    username: Optional[str]
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]

class UserLogin(BaseModel):
    username_or_email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
    role: str

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ForgotPasswordResponse(BaseModel):
    message: str = "If an account exists for this email, a password reset link has been sent."
    dev_reset_url: Optional[str] = None
    dev_token: Optional[str] = None
    dev_note: Optional[str] = None

class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, description="Password must be at least 6 characters long")
    confirm_password: Optional[str] = None

    @field_validator('new_password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v.strip()) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v

class ResetPasswordResponse(BaseModel):
    message: str

class SetupStatusResponse(BaseModel):
    is_initialized: bool

class InitialSetupRequest(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters long")
    confirm_password: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v.strip()) < 6:
            raise ValueError("Password must be at least 6 characters long")
        return v


