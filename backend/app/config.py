from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/fastighetsvisualiserare"
    )
    trafikverket_api_key: str = ""
    # OAuth2 client credentials från Lantmäteriets API-portal
    # (apimanager.lantmateriet.se). Utan dessa används den publika
    # sökproxyn — se app/datasources/detaljplaner.py.
    lantmateriet_consumer_key: str = ""
    lantmateriet_consumer_secret: str = ""
    cors_origins: list[str] = ["http://localhost:5173"]

    # Om satt krävs headern X-API-Key med detta värde för alla skrivande anrop
    # (POST och synkronisering). Lämna tom för att tillåta skrivningar utan nyckel,
    # t.ex. vid lokal utveckling.
    api_write_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
