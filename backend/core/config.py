from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Field names are lowercase — accessed as settings.openai_api_key etc.
    # Pydantic reads from env vars case-insensitively, so DATABASE_URL and database_url both work.
    database_url: str = "postgresql+asyncpg://localhost/deallens"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    secret_key: str = "change-me-in-production"
    environment: str = "development"
    edgar_user_agent: str = "DealLens AI contact@deallens-ai.com"

    # Uppercase aliases so existing code using settings.REDIS_URL still works
    @property
    def REDIS_URL(self) -> str:
        return self.redis_url

    @property
    def DATABASE_URL(self) -> str:
        return self.database_url

    @property
    def OPENAI_API_KEY(self) -> str:
        return self.openai_api_key

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
