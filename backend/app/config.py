from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Algo Trading Learning Lab"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/algo_trading.db"

    # Market data adapter (Phase 11): "dummy" (default) serves this app's own simulated
    # history; "angel_one" selects that adapter's shape, not a working integration yet
    # (see backend/app/adapters/angel_one.py) -- real Phase 12 wiring will need these.
    market_data_provider: str = "dummy"
    angel_one_api_key: str = ""
    angel_one_client_code: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
