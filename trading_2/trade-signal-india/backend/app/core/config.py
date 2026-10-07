from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "TradeSignal India"
    APP_VERSION: str = "0.2.0"
    ENVIRONMENT: Literal["DEVELOPMENT", "MOCK", "PAPER", "LIVE_DATA"] = "DEVELOPMENT"
    DEBUG: bool = False

    HOST: str = "0.0.0.0"
    PORT: int = 8000

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/tradesignal_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    INSTRUMENT: str = "NIFTY"
    BASE_NIFTY_SPOT_PRICE: float = 22600.0
    TIMEFRAMES: list[str] = ["1m", "3m", "5m", "10m", "15m"]
    PRIMARY_TIMEFRAME: str = "5m"
    SIGNAL_SCORE_THRESHOLD: int = 80
    EVALUATION_HORIZONS_MINUTES: list[int] = [1, 3, 5, 10, 15, 20]

    # Current exchange lot sizes; keep configurable for future revisions.
    NIFTY_LOT_SIZE: int = 65
    BANKNIFTY_LOT_SIZE: int = 30
    FINNIFTY_LOT_SIZE: int = 60
    MIDCPNIFTY_LOT_SIZE: int = 120

    # Groww live/historical data.
    GROWW_API_BASE_URL: str = "https://api.groww.in"
    BROKER_API_KEY: str = ""
    BROKER_API_SECRET: str = ""
    BROKER_TOTP_SECRET: str = ""
    BROKER_AUTH_MODE: Literal["TOTP", "APPROVAL"] = "TOTP"
    BROKER_HTTP_TIMEOUT_SECONDS: float = 10.0

    # Upstox API v2 live market analytics
    UPSTOX_API_KEY: str = "da6f3f2c-293d-48d6-84c9-d191d8a24d73"
    UPSTOX_API_SECRET: str = "oyhx3h9ms6"
    UPSTOX_ACCESS_TOKEN: str = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiI4N0E0VEgiLCJqdGkiOiI2YWM0ZGFkYzQ1YWI3NjE0ZjQxNWFjNjUiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlzRXh0ZW5kZWQiOnRydWUsImlhdCI6MTc5MTI4NTk4MCwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxODIyODYwMDAwfQ._pojEYhQvGauKrAG9MMLE4tW2cuTeMjCduiQaJtpLLw"

    # Zerodha Kite Connect credentials
    KITE_API_KEY: str = ""
    KITE_API_SECRET: str = ""
    KITE_ACCESS_TOKEN: str = ""

    # Telegram notification settings
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""

    # Event-risk calendar is supplied as JSON; empty means no scheduled vetoes.
    EVENT_RISK_WINDOW_MINUTES: int = 20
    HIGH_RISK_EVENTS_JSON: str = "[]"

    # Risk/cost controls.
    MAX_DAILY_LOSS_RUPEES: float = 3000.0
    MAX_DAILY_SIGNALS: int = 5
    MIN_RISK_REWARD: float = 1.5
    OPTION_SELL_STT_RATE: float = 0.0015
    OPTION_EXCHANGE_TURNOVER_RATE: float = 0.0003503
    OPTION_STAMP_DUTY_RATE: float = 0.00003
    SEBI_TURNOVER_PER_CRORE: float = 10.0
    BROKERAGE_PER_ORDER: float = 20.0
    GST_RATE: float = 0.18

    DISCLAIMER: str = (
        "Private trading research tool. Signals are algorithmic estimates, "
        "not guaranteed predictions. Past performance does not guarantee future results."
    )

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
