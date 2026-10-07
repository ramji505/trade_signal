from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from app.data.base import MarketDataProvider
from app.broker.groww_auth import GrowwAuthenticator


class GrowwMarketDataProvider(MarketDataProvider):
    """Live/historical Groww provider implementing the project's MarketDataProvider contract."""
    def __init__(self, auth: Optional[GrowwAuthenticator] = None):
        self.auth = auth or GrowwAuthenticator()
        self.connected = False

    async def connect(self) -> bool:
        await self.auth.ensure_authenticated()
        self.connected = True
        return True

    async def disconnect(self) -> None:
        self.connected = False

    async def get_latest_tick(self, symbol: str = "NIFTY") -> dict[str, Any]:
        quote = await self.auth.get_quote(symbol)
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "last_price": float(quote.get("last_price") or quote.get("ltp") or 0),
            "volume": int(quote.get("volume") or quote.get("last_trade_quantity") or 0),
            "bid_price": float(quote.get("bid_price") or 0),
            "offer_price": float(quote.get("offer_price") or 0),
            "open": float(quote.get("open") or 0),
            "high": float(quote.get("high") or 0),
            "low": float(quote.get("low") or 0),
            "is_mock": False,
            "source": "GROWW_LIVE",
        }

    async def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        return await self.auth._get(path, params)

    async def get_historical_candles(self, symbol: str = "NIFTY", timeframe: str = "5m", count: int = 75) -> list[dict[str, Any]]:
        interval = {"1m": "1minute", "3m": "3minute", "5m": "5minute", "10m": "10minute", "15m": "15minute"}.get(timeframe)
        if not interval:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        mins = int(timeframe.rstrip("m"))
        end = datetime.now()
        start = end - timedelta(minutes=(count * mins) + 10)
        payload = await self._get(
            "/v1/historical/candles",
            {
                "exchange": "NSE",
                "segment": "CASH",
                "groww_symbol": f"NSE-{symbol}",
                "start_time": start.strftime("%Y-%m-%d %H:%M:%S"),
                "end_time": end.strftime("%Y-%m-%d %H:%M:%S"),
                "candle_interval": interval,
            },
        )
        records = []
        for row in payload.get("candles", []):
            if len(row) < 6:
                continue
            records.append({"timestamp": row[0], "open": float(row[1]), "high": float(row[2]), "low": float(row[3]), "close": float(row[4]), "volume": float(row[5] or 0)})
        return records[-count:]

    async def get_option_chain(self, symbol: str = "NIFTY", expiry_date: Optional[str] = None) -> dict[str, Any]:
        if not expiry_date:
            now = datetime.now()
            expiry_payload = await self._get("/v1/historical/expiries", {"exchange": "NSE", "underlying_symbol": symbol, "year": now.year})
            future = sorted([e for e in expiry_payload.get("expiries", []) if e >= now.date().isoformat()])
            if not future:
                raise RuntimeError("No future expiry available")
            expiry_date = future[0]
        return await self._get(f"/v1/option-chain/exchange/NSE/underlying/{symbol}", {"expiry_date": expiry_date})
