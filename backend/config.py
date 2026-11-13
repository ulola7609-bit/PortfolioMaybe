from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, AnyHttpUrl

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    app_env: str = "development"
    secret_key: str = Field(min_length=32, default="CHANGE_ME_TO_A_RANDOM_32_CHAR_SECRET")
    bot_token: str = ""
    admin_id: int = 0
    bot_username: str = "memiasma_bot"
    mini_app_url: str = "http://localhost:5173"
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/neonterminal"
    cors_origins: str = "http://localhost:5173"
    telegram_webhook_secret: str = ""
    telegram_webhook_url: str = ""
    xrocket_api_key: str = ""
    xrocket_base_url: str = "https://pay.api.testnet.xrocket.exchange"
    xrocket_webhook_secret: str = ""
    xrocket_live_enabled: bool = False
    default_currency: str = "USDT"
    priority_price_usd: int = 15
    benchmark_custom_url: str = ""
    benchmark_public_url: str = "https://www.google.com/generate_204"
    rate_limit_per_minute: int = 60

    @property
    def cors_list(self) -> list[str]:
        return [x.strip() for x in self.cors_origins.split(",") if x.strip()]

settings = Settings()
