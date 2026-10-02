from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Algo Trading Learning Lab"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/algo_trading.db"

    # Market data adapter: "dummy" (default) serves this app's own simulated history;
    # "angel_one" logs into a real Angel One (SmartAPI) account for real NSE candles/LTP
    # (see backend/app/adapters/angel_one.py); "upstox" reads daily candles with an Upstox
    # Analytics Token (see backend/app/adapters/upstox.py). Never commit real values for these -- keep
    # them only in your local .env (already gitignored).
    market_data_provider: str = "dummy"
    angel_one_api_key: str = ""
    angel_one_client_code: str = ""
    angel_one_pin: str = ""
    angel_one_totp_secret: str = ""

    # Upstox: a read-only "Analytics Token" (Developer Apps page -> Analytics tab), valid for
    # a year, no static IP needed. Local .env only, same as the Angel One values above.
    upstox_analytics_token: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
