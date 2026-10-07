from datetime import datetime, timezone
from typing import NamedTuple, Optional
import pandas as pd


class CandleData(NamedTuple):
    timestamp: datetime
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    vwap: Optional[float] = None


class CandleBuilder:
    """
    Aggregates incoming ticks or 1-minute base candles into multi-timeframe candles (1m, 3m, 5m, 10m, 15m).
    Aligns candle intervals strictly with market start time (09:15 IST / 03:45 UTC).
    """

    SUPPORTED_TIMEFRAMES = ["1m", "3m", "5m", "10m", "15m"]

    @staticmethod
    def resample_candles(df_1m: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
        """
        Resamples a 1-minute OHLCV DataFrame into the target timeframe (e.g., '3m', '5m', '10m', '15m').
        df_1m must have datetime index and columns ['open', 'high', 'low', 'close', 'volume'].
        """
        if target_timeframe == "1m":
            resampled = df_1m.copy()
        else:
            minutes_map = {
                "3m": "3min",
                "5m": "5min",
                "10m": "10min",
                "15m": "15min"
            }

            freq = minutes_map.get(target_timeframe)
            if not freq:
                raise ValueError(f"Unsupported timeframe: {target_timeframe}")

            # Resample OHLCV
            resampled = df_1m.resample(freq, origin='start').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            }).dropna()

        # Calculate session VWAP (handles zero-volume index spot candles safely)
        resampled['typical_price'] = (resampled['high'] + resampled['low'] + resampled['close']) / 3.0
        if resampled['volume'].sum() > 0:
            resampled['pv'] = resampled['typical_price'] * resampled['volume']
            resampled['cum_pv'] = resampled['pv'].cumsum()
            resampled['cum_vol'] = resampled['volume'].cumsum()
            resampled['vwap'] = resampled['cum_pv'] / resampled['cum_vol'].replace(0, 1)
            resampled.drop(columns=['typical_price', 'pv', 'cum_pv', 'cum_vol'], inplace=True)
        else:
            resampled['vwap'] = resampled['typical_price'].expanding().mean()
            resampled.drop(columns=['typical_price'], inplace=True)

        return resampled
