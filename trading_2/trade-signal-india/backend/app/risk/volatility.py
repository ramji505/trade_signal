from dataclasses import dataclass
from typing import Literal
import pandas as pd


@dataclass
class VolatilityState:
    atr: float
    atr_pct: float
    regime: Literal["VERY_LOW", "LOW", "NORMAL", "HIGH", "EXTREME"]
    is_tradable: bool
    risk_adjustment_factor: float


class VolatilityEngine:
    """
    Evaluates intraday volatility conditions for NIFTY:
    - Normal NIFTY 5-minute ATR: ~15 to 35 points
    - High: 35 to 60 points
    - Extreme: > 60 points (often during panic/budget events -> risk adjustment or WAIT)
    """

    @staticmethod
    def evaluate(current_price: float, atr_value: float) -> VolatilityState:
        atr_pct = (atr_value / current_price) * 100.0 if current_price > 0 else 0.1

        if atr_value < 10.0:
            regime = "VERY_LOW"
            factor = 1.2  # Slightly widen SL to avoid noise
            tradable = True
        elif atr_value <= 35.0:
            regime = "NORMAL"
            factor = 1.0
            tradable = True
        elif atr_value <= 55.0:
            regime = "HIGH"
            factor = 1.25
            tradable = True
        else:
            regime = "EXTREME"
            factor = 1.5
            tradable = False  # Unsafe / Event volatility -> wait

        return VolatilityState(
            atr=round(atr_value, 2),
            atr_pct=round(atr_pct, 4),
            regime=regime,
            is_tradable=tradable,
            risk_adjustment_factor=factor
        )
