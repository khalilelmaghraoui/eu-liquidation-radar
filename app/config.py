# app/config.py
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List

class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    ADMIN_USER_IDS: List[int] = Field(default_factory=list)
    BASE_CITY: str = "Marseille"
    BASE_LAT: float = 43.2965
    BASE_LON: float = 5.3698

    DATABASE_URL: str = "sqlite+sqlite:///./radar.db"

    LOG_LEVEL: str = "INFO"
    HOURLY_SCRAPE_MINUTE: int = 7

    WEB_HOST: str = "0.0.0.0"
    WEB_PORT: int = 8000

    DEFAULT_FEES_PCT: float = 0.12
    DEFAULT_SHIP_EUR_PER_KG: float = 1.8
    DEFAULT_FIXED_SHIP_EUR: float = 25.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
