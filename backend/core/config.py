from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://localhost/deallens"
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENAI_API_KEY: str
    SECRET_KEY: str = "change-me-in-production"
    ENVIRONMENT: str = "development"
    EDGAR_USER_AGENT: str = "DealLens AI contact@deallens-ai.com"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
