import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "NetVision API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "anothertopsysecretkey9876543210")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        x.strip() for x in os.getenv("BACKEND_CORS_ORIGINS", "*").split(",") if x.strip()
    ]
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://admin:supersecretpassword123@localhost:5432/netvision"
    )

    class Config:
        case_sensitive = True

settings = Settings()
