from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Algo Trading Learning Lab"
    log_level: str = "INFO"
    database_url: str = "sqlite:///./data/algo_trading.db"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
