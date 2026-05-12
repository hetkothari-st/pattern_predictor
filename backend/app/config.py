from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    price_ws_url: str = ""
    price_ws_format: str = "generic"  # generic | binance | mt
    default_symbol: str = "BTCUSDT"
    default_timeframe: str = "1m"
    bar_history: int = 1000
    model_path: str = "../data/models/v1.pt"
    patterns_yaml: str = "app/knowledge/patterns.yaml"
    predictions_db: str = "sqlite:///../data/predictions.sqlite"
    # MT Data Feed credentials (anonymous works for market data).
    mt_login_id: str = ""
    mt_password: str = ""
    # JSON list of {Tkn, Xchg, Symbol, FeedType} dicts. FeedType 1=Index/Touchline,
    # 2=Depth. Symbol is what surfaces in the chart UI.
    # Example: [{"Tkn":"26000","Xchg":"NSE","Symbol":"NIFTY50","FeedType":1}]
    mt_subscriptions: str = ""
    # When true, every closed bar is appended to data/ohlcv/{symbol}_{tf}.csv
    # so live runs accumulate a training corpus for app.ml.train.
    record_ohlcv: bool = False
    ohlcv_dir: str = "../data/ohlcv"


settings = Settings()
