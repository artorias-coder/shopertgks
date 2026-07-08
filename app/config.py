from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import List


class Settings(BaseSettings):
    BOT_TOKEN: str
    ADMIN_IDS: str = ""
    SUPERADMIN_ID: str = ""

    @property
    def admin_ids(self) -> List[int]:
        if not self.ADMIN_IDS:
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]

    @property
    def superadmin_id(self) -> int | None:
        if not self.SUPERADMIN_ID:
            return None
        return int(self.SUPERADMIN_ID)

    DATABASE_URL: str
    DATABASE_URL_SYNC: str
    REDIS_URL: str

    GOOGLE_SHEETS_ID: str | None = None
    GOOGLE_CREDENTIALS_JSON: str | None = None
    GOOGLE_SYNC_INTERVAL_MINUTES: int = 5

    LIVESKLAD_API_TOKEN: str | None = None
    LIVESKLAD_API_LOGIN: str | None = None
    LIVESKLAD_API_PASSWORD: str | None = None
    LIVESKLAD_SHOP_ID: str | None = None
    LIVESKLAD_TYPE_ORDER_ID: str | None = None
    LIVESKLAD_TRADEIN_TYPE_ORDER_ID: str | None = None
    LIVESKLAD_BASE_URL: str = "https://api.livesklad.com"

    WEBHOOK_URL: str | None = None
    WEBHOOK_SECRET: str | None = None

    WEBAPP_URL: str | None = None
    CHANNEL_ID: str | None = None

    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
