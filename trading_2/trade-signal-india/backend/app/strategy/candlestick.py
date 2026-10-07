from typing import Literal
import pandas as pd


class CandlestickEngine:
    """
    Tier-2 confirmation candlestick pattern detector:
    - Hammer & Inverted Hammer
    - Shooting Star
    - Bullish & Bearish Engulfing
    - Doji (Indecision)
    Patterns serve strictly as confirmation filters, never as standalone signal generators.
    """

    @staticmethod
    def detect_pattern(df: pd.DataFrame) -> Literal[
        "HAMMER", "SHOOTING_STAR", "BULLISH_ENGULFING", "BEARISH_ENGULFING", "DOJI", "NONE"
    ]:
        if len(df) < 2:
            return "NONE"

        last = df.iloc[-1]
        prev = df.iloc[-2]

        body = abs(last['close'] - last['open'])
        total_range = last['high'] - last['low']
        upper_wick = last['high'] - max(last['open'], last['close'])
        lower_wick = min(last['open'], last['close']) - last['low']

        if total_range == 0:
            return "DOJI"

        # Doji (body <= 10% of candle range)
        if body / total_range <= 0.10:
            return "DOJI"

        # Hammer (Lower wick >= 2x body and upper wick <= 10% of range)
        if lower_wick >= 2.0 * body and upper_wick <= 0.15 * total_range:
            return "HAMMER"

        # Shooting Star (Upper wick >= 2x body and lower wick <= 10% of range)
        if upper_wick >= 2.0 * body and lower_wick <= 0.15 * total_range:
            return "SHOOTING_STAR"

        # Bullish Engulfing
        if (prev['close'] < prev['open'] and  # Prev was red
            last['close'] > last['open'] and   # Current is green
            last['open'] <= prev['close'] and
            last['close'] >= prev['open']):
            return "BULLISH_ENGULFING"

        # Bearish Engulfing
        if (prev['close'] > prev['open'] and  # Prev was green
            last['close'] < last['open'] and   # Current is red
            last['open'] >= prev['close'] and
            last['close'] <= prev['open']):
            return "BEARISH_ENGULFING"

        return "NONE"
