from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    ANTHROPIC_API_KEY: str = ""
    MYPLANS_API_URL: str = "http://localhost:8095"

    PORT: int = 8099
    HOST: str = "0.0.0.0"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    PDF_DPI: int = 150
    MAX_PAGES: int = 20
    CLAUDE_MODEL: str = "claude-sonnet-4-6"

    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
