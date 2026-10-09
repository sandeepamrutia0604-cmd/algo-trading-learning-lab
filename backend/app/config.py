from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .paths import data_dir, is_desktop

DEFAULT_DATABASE_URL = "sqlite:///./data/algo_trading.db"


class Settings(BaseSettings):
    app_name: str = "Algo Trading Learning Lab"
    log_level: str = "INFO"
    database_url: str = DEFAULT_DATABASE_URL

    # The Windows download: simulated stocks and CSV files only. No .env is read, no broker is ever
    # contacted (the broker routes answer 404), and the database lives in a per-user folder (paths.py).
    desktop_mode: bool = Field(default_factory=is_desktop, validation_alias="ALGO_DESKTOP")

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

    model_config = SettingsConfigDict(env_file=None if is_desktop() else ".env", extra="ignore", populate_by_name=True)

    @model_validator(mode="after")
    def _desktop_defaults(self):
        if self.desktop_mode:
            self.market_data_provider = "dummy"
            if self.database_url == DEFAULT_DATABASE_URL:
                self.database_url = f"sqlite:///{(data_dir() / 'algo_trading.db').as_posix()}"
        return self


settings = Settings()
