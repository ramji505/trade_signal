from dataclasses import dataclass
from typing import Literal
import pandas as pd


@dataclass
class PriceActionResult:
    action_type: Literal[
        "BREAKOUT_BULLISH", "BREAKOUT_BEARISH",
        "RETEST_BULLISH", "RETEST_BEARISH",
        "REJECTION_TOP", "REJECTION_BOTTOM",
        "CONSOLIDATION", "NEUTRAL"
    ]
    rejection_wick_ratio: float
    description: str


class PriceActionEngine:
    """
    Price Action detector:
    - Breakout above resistance / Breakdown below support
    - Retest of broken levels with price rejection
    - Rejection pinbars / wicks (> 2x body)
    - Consolidation / narrow range detection
    """

    @staticmethod
    def evaluate(df: pd.DataFrame, key_resistance: float, key_support: float) -> PriceActionResult:
        if len(df) < 5:
            return PriceActionResult("NEUTRAL", 0.0, "Insufficient candle history")

        last = df.iloc[-1]
        prev = df.iloc[-2]

        body = abs(last['close'] - last['open'])
        upper_wick = last['high'] - max(last['open'], last['close'])
        lower_wick = min(last['open'], last['close']) - last['low']
        total_range = last['high'] - last['low']

        # Rejection wick detection
        wick_ratio = (upper_wick / body) if body > 0 else 1.0
        lower_wick_ratio = (lower_wick / body) if body > 0 else 1.0

        # Bullish Rejection from Support
        if lower_wick_ratio >= 2.0 and abs(last['low'] - key_support) <= (total_range * 0.5):
            return PriceActionResult("REJECTION_BOTTOM", lower_wick_ratio, "Strong buying rejection from support")

        # Bearish Rejection from Resistance
        if wick_ratio >= 2.0 and abs(last['high'] - key_resistance) <= (total_range * 0.5):
            return PriceActionResult("REJECTION_TOP", wick_ratio, "Strong selling rejection from resistance")

        # Bullish Breakout
        if prev['close'] <= key_resistance and last['close'] > key_resistance:
            return PriceActionResult("BREAKOUT_BULLISH", wick_ratio, "Bullish breakout above key level")

        # Bearish Breakdown
        if prev['close'] >= key_support and last['close'] < key_support:
            return PriceActionResult("BREAKOUT_BEARISH", lower_wick_ratio, "Bearish breakdown below key level")

        # Retest detection
        if last['low'] <= key_resistance and last['close'] > key_resistance and prev['close'] > key_resistance:
            return PriceActionResult("RETEST_BULLISH", lower_wick_ratio, "Successful bullish retest of broken level")

        if last['high'] >= key_support and last['close'] < key_support and prev['close'] < key_support:
            return PriceActionResult("RETEST_BEARISH", wick_ratio, "Successful bearish retest of broken level")

        # Consolidation check (ATR contraction)
        avg_range = (df['high'] - df['low']).rolling(5).mean().iloc[-1]
        if total_range < avg_range * 0.5:
            return PriceActionResult("CONSOLIDATION", 0.0, "Price compressing in tight consolidation range")

        return PriceActionResult("NEUTRAL", 0.0, "Standard price progression")
