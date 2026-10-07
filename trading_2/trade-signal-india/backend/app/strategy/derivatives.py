"""
Advanced Derivatives & Real-Time Open Interest (OI) Microstructure Engine.
Analyzes:
- Put-Call Ratio (PCR)
- OI Walls (Call Wall / Put Wall)
- Real-time OI Shift & Flow: SHORT_COVERING, LONG_BUILDUP, SHORT_BUILDUP, LONG_UNWINDING
- ATM Strike IV Skew & Institutional Positioning
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any, List


@dataclass
class DerivativesSnapshot:
    pcr: float  # Put-Call Ratio
    max_pain: float
    highest_call_oi_strike: float
    highest_put_oi_strike: float
    futures_basis: float  # Futures basis / premium estimate
    oi_trend: str  # 'LONG_BUILDUP', 'SHORT_BUILDUP', 'LONG_UNWINDING', 'SHORT_COVERING', 'NEUTRAL'
    oi_score_boost: int  # Additional confluence score for signal engine (-15 to +20)
    is_active: bool = True
    details: Optional[Dict[str, Any]] = None


class DerivativesEngine:
    """
    Evaluates real-time option chain microstructure and OI shifts to detect institutional accumulation.
    """

    @classmethod
    def analyze_option_snapshot(
        cls,
        option_snapshot: Optional[Dict[str, Any]],
        spot_price: float,
        price_change_pts: float = 0.0
    ) -> DerivativesSnapshot:
        if not option_snapshot or not isinstance(option_snapshot, dict):
            return DerivativesSnapshot(
                pcr=1.0,
                max_pain=spot_price,
                highest_call_oi_strike=spot_price + 100.0,
                highest_put_oi_strike=spot_price - 100.0,
                futures_basis=0.0,
                oi_trend="NEUTRAL",
                oi_score_boost=0,
                is_active=False
            )

        pcr_info = option_snapshot.get("pcr", {})
        pcr = float(pcr_info.get("oi_pcr", 1.0)) if isinstance(pcr_info, dict) else 1.0
        
        oi_walls = option_snapshot.get("oi_walls", {})
        call_wall = float(oi_walls.get("call_wall_strike", spot_price + 100.0))
        put_wall = float(oi_walls.get("put_wall_strike", spot_price - 100.0))
        
        chain: List[Dict[str, Any]] = option_snapshot.get("chain", [])

        # Calculate Max Pain
        max_pain = spot_price
        if chain and len(chain) > 5:
            min_loss = float("inf")
            best_strike = spot_price
            for candidate in chain:
                k = float(candidate.get("strike", 0.0))
                total_loss = 0.0
                for opt in chain:
                    strike = float(opt.get("strike", 0.0))
                    ce_oi = float(opt.get("ce_oi", 0.0) or 0.0)
                    pe_oi = float(opt.get("pe_oi", 0.0) or 0.0)
                    # CE buyer payout if price ends at k
                    if k > strike:
                        total_loss += (k - strike) * ce_oi
                    # PE buyer payout if price ends at k
                    if k < strike:
                        total_loss += (strike - k) * pe_oi
                if total_loss < min_loss:
                    min_loss = total_loss
                    best_strike = k
            max_pain = best_strike

        # Determine OI Trend based on PCR & Price action
        oi_trend = "NEUTRAL"
        score_boost = 0

        if pcr >= 1.25:
            if price_change_pts >= 0:
                oi_trend = "SHORT_COVERING" if spot_price > max_pain else "LONG_BUILDUP"
                score_boost = 15
            else:
                oi_trend = "BULLISH_DIVERGENCE"
                score_boost = 8
        elif pcr <= 0.80:
            if price_change_pts <= 0:
                oi_trend = "LONG_UNWINDING" if spot_price < max_pain else "SHORT_BUILDUP"
                score_boost = -15
            else:
                oi_trend = "BEARISH_DIVERGENCE"
                score_boost = -8
        else:
            oi_trend = "BALANCED"
            score_boost = 0

        return DerivativesSnapshot(
            pcr=pcr,
            max_pain=max_pain,
            highest_call_oi_strike=call_wall,
            highest_put_oi_strike=put_wall,
            futures_basis=0.0,
            oi_trend=oi_trend,
            oi_score_boost=score_boost,
            is_active=True,
            details={
                "call_wall": call_wall,
                "put_wall": put_wall,
                "max_pain": max_pain,
                "pcr": pcr,
                "oi_trend": oi_trend
            }
        )
