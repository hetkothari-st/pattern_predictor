from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    price_ws_url: str = ""
    price_ws_format: str = "generic"  # generic | binance
    default_symbol: str = "BTCUSDT"
    default_timeframe: str = "1m"
    bar_history: int = 1000
    model_path: str = "../data/models/v1.pt"
    patterns_yaml: str = "app/knowledge/patterns.yaml"
    predictions_db: str = "sqlite:///../data/predictions.sqlite"


settings = Settings()
