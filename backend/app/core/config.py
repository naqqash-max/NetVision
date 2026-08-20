import os
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "NetVision API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "anothertopsysecretkey9876543210")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    RESET_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "15"))
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # SMTP / Email Configuration
    SMTP_HOST: str = os.getenv("SMTP_HOST", "mailpit")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "1025"))
    SMTP_USERNAME: str = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL: str = os.getenv("SMTP_FROM_EMAIL", "noreply@netvision.local")
    SMTP_FROM_NAME: str = os.getenv("SMTP_FROM_NAME", "NetVision Operations Center")
    SMTP_TLS: bool = os.getenv("SMTP_TLS", "false").lower() in ("true", "1", "yes")
    SMTP_SSL: bool = os.getenv("SMTP_SSL", "false").lower() in ("true", "1", "yes")
    EMAIL_ENABLED: bool = os.getenv("EMAIL_ENABLED", "true").lower() in ("true", "1", "yes")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        x.strip() for x in os.getenv(
            "BACKEND_CORS_ORIGINS", 
            "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000"
        ).split(",") if x.strip()
    ]
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://admin:supersecretpassword123@localhost:5432/netvision"
    )

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.ENVIRONMENT == "production" and "PYTEST_CURRENT_TEST" not in os.environ:
            # SECRET_KEY validation
            if not self.SECRET_KEY or self.SECRET_KEY.strip() == "" or self.SECRET_KEY == "anothertopsysecretkey9876543210":
                raise ValueError("SECRET_KEY must be configured and cannot use the development fallback in production!")
            
            # Database password validation
            if not self.DATABASE_URL or "supersecretpassword123" in self.DATABASE_URL or "@" not in self.DATABASE_URL:
                raise ValueError("DATABASE_URL must be configured with a secure password in production (cannot use development fallback 'supersecretpassword123')!")
            
            # SMTP validation when EMAIL_ENABLED is True
            if self.EMAIL_ENABLED:
                if not self.SMTP_HOST or self.SMTP_HOST.strip() == "" or self.SMTP_HOST == "mailpit":
                    raise ValueError("SMTP_HOST must be configured and cannot use the 'mailpit' fallback in production when EMAIL_ENABLED is True!")
                if not self.SMTP_USERNAME or self.SMTP_USERNAME.strip() == "":
                    raise ValueError("SMTP_USERNAME must be configured in production when EMAIL_ENABLED is True!")
                if not self.SMTP_PASSWORD or self.SMTP_PASSWORD.strip() == "":
                    raise ValueError("SMTP_PASSWORD must be configured in production when EMAIL_ENABLED is True!")
                if not self.SMTP_FROM_EMAIL or self.SMTP_FROM_EMAIL.strip() == "":
                    raise ValueError("SMTP_FROM_EMAIL must be configured in production when EMAIL_ENABLED is True!")
        return self

    model_config = SettingsConfigDict(case_sensitive=True)

settings = Settings()
