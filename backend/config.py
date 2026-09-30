from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    youtube_api_key: str | None = None
    google_maps_api_key: str | None = None
    all_trails_api_key: str | None = None
    database_url: str = "sqlite:///./summit_up.db"
    cache_ttl_seconds: int = 300
    metrics_cache_ttl_seconds: int = 900
    allowed_origins: str = "http://localhost:5173"
    default_country: str = "new-zealand"
    default_query: str = "hikes in Auckland, New Zealand"
    frontend_dist: Path = Path(__file__).resolve().parent.parent / "frontend" / "dist"

    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
