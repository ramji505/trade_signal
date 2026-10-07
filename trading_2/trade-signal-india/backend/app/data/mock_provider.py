from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Dict, List
import numpy as np
import pandas as pd
from app.data.base import MarketDataProvider
from app.data.candle_builder import CandleBuilder


class MockNiftyProvider(MarketDataProvider):
    """
    Stateful Continuous Market Data Provider for NIFTY 50 Intraday.
    Maintains a single persistent, continuous price sequence and updates live ticks
    without jumping randomly across page refreshes.
    """

    def __init__(self, base_price: float = 22600.0, seed: int = 42):
        self.base_price = base_price
        self.current_price = base_price
        self.seed = seed
        self.connected = False
        self._history_1m: Optional[pd.DataFrame] = None
        self._last_tick_time: Optional[datetime] = None
        self._init_stateful_history()

    def _init_stateful_history(self, num_candles: int = 400):
        """Generates initial historical session once with fixed seed."""
        np.random.seed(self.seed)
        base_date = datetime.now().date()
        start_time = datetime(base_date.year, base_date.month, base_date.day, 9, 15, 0)
        timestamps = [start_time + timedelta(minutes=i) for i in range(num_candles)]

        # Smooth, realistic intraday walk (+- 0.3% max deviation)
        returns = np.random.normal(0.00001, 0.00008, num_candles)
        price_curve = self.base_price * np.exp(np.cumsum(returns))

        data = []
        for i, ts in enumerate(timestamps):
            close_p = float(price_curve[i])
            spread = np.random.uniform(1.5, 4.0)
            open_p = float(price_curve[i-1]) if i > 0 else close_p - 1.0
            high_p = max(open_p, close_p) + np.random.uniform(0.5, spread * 0.5)
            low_p = min(open_p, close_p) - np.random.uniform(0.5, spread * 0.5)
            volume = float(np.random.randint(1800, 4500))

            data.append({
                "timestamp": ts,
                "open": round(open_p, 2),
                "high": round(high_p, 2),
                "low": round(low_p, 2),
                "close": round(close_p, 2),
                "volume": volume
            })

        df = pd.DataFrame(data).set_index("timestamp")
        self._history_1m = df
        self.current_price = float(df["close"].iloc[-1])
        self._last_tick_time = timestamps[-1]

    async def connect(self) -> bool:
        self.connected = True
        return True

    async def disconnect(self) -> None:
        self.connected = False

    async def get_latest_tick(self, symbol: str = "NIFTY") -> dict[str, Any]:
        # Micro tick update (+- 0.5 to 1.5 points)
        delta = np.random.normal(0.05, 0.4)
        self.current_price = round(self.current_price + delta, 2)
        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "last_price": self.current_price,
            "volume": 1250,
            "is_mock": True
        }

    async def get_historical_candles(
        self, symbol: str = "NIFTY", timeframe: str = "5m", count: int = 75
    ) -> list[dict[str, Any]]:
        """
        Returns continuous, resampled candles from stateful history with live micro-tick continuity.
        """
        if self._history_1m is None:
            self._init_stateful_history()

        df_1m = self._history_1m.copy()
        
        # Keep last candle synced with current price
        last_idx = df_1m.index[-1]
        df_1m.loc[last_idx, "close"] = self.current_price
        if self.current_price > df_1m.loc[last_idx, "high"]:
            df_1m.loc[last_idx, "high"] = self.current_price
        if self.current_price < df_1m.loc[last_idx, "low"]:
            df_1m.loc[last_idx, "low"] = self.current_price

        # Resample to target timeframe
        df_target = CandleBuilder.resample_candles(df_1m, timeframe)
        df_target = df_target.tail(count)

        records = []
        for ts, row in df_target.iterrows():
            records.append({
                "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "timeframe": timeframe,
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
                "vwap": float(row.get("vwap", row["close"]))
            })

        return records

    async def get_option_chain(self, symbol: str = "NIFTY", expiry_date: str | None = None) -> dict[str, Any]:
        from app.options.option_chain import generate_synthetic_option_chain
        return generate_synthetic_option_chain(self.current_price)
