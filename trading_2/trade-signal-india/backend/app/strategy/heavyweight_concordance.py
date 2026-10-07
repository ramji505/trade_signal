"""
Heavyweight & Sectoral Concordance Engine for NIFTY 50.
Evaluates trend alignment across NIFTY's top driving components:
- HDFCBANK, RELIANCE, ICICIBANK, INFY, TCS, and BANKNIFTY.
Filters out false breakouts when index moves without institutional heavyweight backing.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Literal


@dataclass
class HeavyweightConcordanceResult:
    concordance_score: float  # -1.0 (All Bearish) to +1.0 (All Bullish)
    is_aligned_for_buy: bool
    is_aligned_for_sell: bool
    leading_stocks: List[str]
    lagging_stocks: List[str]
    details: Dict[str, str]
    recommendation: Literal["PASS", "CAUTION", "VETO"]


class HeavyweightConcordanceEngine:
    # NIFTY 50 Weightings Approximation
    WEIGHTS = {
        "HDFCBANK": 0.30,
        "RELIANCE": 0.25,
        "ICICIBANK": 0.20,
        "INFY": 0.15,
        "BANKNIFTY": 0.10
    }

    @classmethod
    def evaluate(
        cls,
        component_trends: Dict[str, str], # Symbol -> "BULLISH" / "BEARISH" / "NEUTRAL"
        signal_direction: Literal["BUY", "SELL"]
    ) -> HeavyweightConcordanceResult:
        if not component_trends:
            return HeavyweightConcordanceResult(
                concordance_score=0.0,
                is_aligned_for_buy=True,
                is_aligned_for_sell=True,
                leading_stocks=[],
                lagging_stocks=[],
                details={},
                recommendation="PASS"
            )

        total_weight = 0.0
        weighted_direction_score = 0.0
        leading = []
        lagging = []

        for symbol, weight in cls.WEIGHTS.items():
            trend = component_trends.get(symbol, "NEUTRAL").upper()
            total_weight += weight
            if "BULL" in trend:
                weighted_direction_score += weight
                if signal_direction == "BUY":
                    leading.append(symbol)
                else:
                    lagging.append(symbol)
            elif "BEAR" in trend:
                weighted_direction_score -= weight
                if signal_direction == "SELL":
                    leading.append(symbol)
                else:
                    lagging.append(symbol)
            else:
                lagging.append(symbol)

        normalized_score = weighted_direction_score / total_weight if total_weight > 0 else 0.0

        is_buy_aligned = normalized_score >= 0.25
        is_sell_aligned = normalized_score <= -0.25

        if signal_direction == "BUY":
            if normalized_score >= 0.40:
                rec = "PASS"
            elif normalized_score >= 0.0:
                rec = "CAUTION"
            else:
                rec = "VETO"
        else: # SELL
            if normalized_score <= -0.40:
                rec = "PASS"
            elif normalized_score <= 0.0:
                rec = "CAUTION"
            else:
                rec = "VETO"

        return HeavyweightConcordanceResult(
            concordance_score=round(normalized_score, 2),
            is_aligned_for_buy=is_buy_aligned,
            is_aligned_for_sell=is_sell_aligned,
            leading_stocks=leading,
            lagging_stocks=lagging,
            details=component_trends,
            recommendation=rec
        )
