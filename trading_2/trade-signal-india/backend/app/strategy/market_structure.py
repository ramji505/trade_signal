from dataclasses import dataclass
from typing import Literal, Optional
import pandas as pd


@dataclass
class MarketStructureResult:
    trend_type: Literal["HH_HL", "LH_LL", "RANGE", "UNDEFINED"]
    structure_event: Optional[Literal["BOS_BULLISH", "BOS_BEARISH", "CHOCH_BULLISH", "CHOCH_BEARISH", "NONE"]]
    last_swing_high: float
    last_swing_low: float
    strength: float  # 0.0 to 1.0


class MarketStructure:
    """
    Mathematical price structure engine:
    - Detects swing highs and swing lows
    - Identifies Higher Highs / Higher Lows (Uptrend) vs Lower Highs / Lower Lows (Downtrend)
    - Break of Structure (BOS): price closing beyond recent structural swing high/low in direction of trend
    - Change of Character (CHOCH): price breaking opposite structural level signaling potential trend shift
    """

    @staticmethod
    def identify_swings(df: pd.DataFrame, window: int = 3) -> tuple[pd.Series, pd.Series]:
        """Identifies local swing highs and swing lows."""
        highs = df['high']
        lows = df['low']

        swing_high = (highs == highs.rolling(2 * window + 1, center=True).max())
        swing_low = (lows == lows.rolling(2 * window + 1, center=True).min())

        return swing_high, swing_low

    @classmethod
    def analyze_structure(cls, df: pd.DataFrame) -> MarketStructureResult:
        if len(df) < 15:
            return MarketStructureResult("UNDEFINED", "NONE", 0.0, 0.0, 0.0)

        swing_highs_mask, swing_lows_mask = cls.identify_swings(df, window=2)
        sh_prices = df.loc[swing_highs_mask, 'high'].values
        sl_prices = df.loc[swing_lows_mask, 'low'].values

        if len(sh_prices) < 2 or len(sl_prices) < 2:
            last_close = float(df['close'].iloc[-1])
            return MarketStructureResult("RANGE", "NONE", last_close * 1.01, last_close * 0.99, 0.5)

        last_sh = sh_prices[-1]
        prev_sh = sh_prices[-2]
        last_sl = sl_prices[-1]
        prev_sl = sl_prices[-2]

        current_close = float(df['close'].iloc[-1])

        # Trend Determination
        is_bullish = (last_sh >= prev_sh) and (last_sl >= prev_sl)
        is_bearish = (last_sh <= prev_sh) and (last_sl <= prev_sl)

        trend_type: Literal["HH_HL", "LH_LL", "RANGE", "UNDEFINED"] = (
            "HH_HL" if is_bullish else ("LH_LL" if is_bearish else "RANGE")
        )

        # BOS / CHOCH Detection
        structure_event: Literal["BOS_BULLISH", "BOS_BEARISH", "CHOCH_BULLISH", "CHOCH_BEARISH", "NONE"] = "NONE"

        if current_close > last_sh:
            structure_event = "BOS_BULLISH" if is_bullish else "CHOCH_BULLISH"
        elif current_close < last_sl:
            structure_event = "BOS_BEARISH" if is_bearish else "CHOCH_BEARISH"

        strength = 0.85 if structure_event != "NONE" else (0.70 if trend_type in ["HH_HL", "LH_LL"] else 0.40)

        return MarketStructureResult(
            trend_type=trend_type,
            structure_event=structure_event,
            last_swing_high=float(last_sh),
            last_swing_low=float(last_sl),
            strength=strength
        )
