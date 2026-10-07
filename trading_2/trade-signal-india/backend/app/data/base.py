from abc import ABC, abstractmethod
from typing import Any


class MarketDataProvider(ABC):
    """Abstract interface for all market data providers (Mock, Broker, Direct)."""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the market data feed."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Close connection cleanly."""
        pass

    @abstractmethod
    async def get_latest_tick(self, symbol: str) -> dict[str, Any]:
        """Fetch latest price tick."""
        pass

    @abstractmethod
    async def get_historical_candles(self, symbol: str, timeframe: str, count: int) -> list[dict[str, Any]]:
        """Fetch historical candle series."""
        pass
