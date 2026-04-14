from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://deallens:deallens_secret@localhost:5432/deallens"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    environment: str = "development"
    secret_key: str = "change-me-in-production"
    edgar_user_agent: str = "DealLens AI contact@deallens-ai.com"


settings = Settings()
