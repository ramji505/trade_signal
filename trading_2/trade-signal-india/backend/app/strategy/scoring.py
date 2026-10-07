from dataclasses import dataclass
from typing import Literal, Dict, Any, Optional


@dataclass
class ScoringBreakdown:
    tier1_structure_score: int       # 45 pts
    tier2_indicator_score: int       # 30 pts
    tier3_options_score: int         # 25 pts
    tier4_risk_penalty: int          # 0..30 pts
    total_score: int
    quality: Literal["NO_TRADE", "WEAK", "MODERATE", "STRONG", "VERY_STRONG"]
    details: Dict[str, Any]


class SignalScorer:
    """Single 100-point score with options microstructure as a first-class input."""

    @staticmethod
    def calculate_score(
        direction: Literal["BUY", "SELL"],
        mtf_aligned: bool,
        mtf_concordance: int,
        structure_type: str,
        price_vs_vwap: bool,
        ema_aligned: bool,
        volume_expanding: bool,
        rsi_value: float,
        candlestick_pattern: str,
        headroom_available: bool,
        volatility_tradable: bool,
        event_penalty: int,
        pcr: Optional[float] = None,
        call_wall: Optional[float] = None,
        put_wall: Optional[float] = None,
        current_price: Optional[float] = None,
        atm_iv: Optional[float] = None,
        spread_pct: Optional[float] = None,
        liquidity_status: Optional[str] = None,
    ) -> ScoringBreakdown:
        details: Dict[str, Any] = {}
        t1 = 0
        t2 = 0
        t3 = 0
        penalty = 0

        t1 += 20 if mtf_aligned else max(0, min(20, round(mtf_concordance * 0.2)))
        details["mtf"] = t1

        aligned_structure = (direction == "BUY" and structure_type in {"HH_HL", "BOS_BULLISH", "CHOCH_BULLISH"}) or (direction == "SELL" and structure_type in {"LH_LL", "BOS_BEARISH", "CHOCH_BEARISH"})
        if aligned_structure:
            t1 += 15
        if price_vs_vwap:
            t1 += 10
        details["structure"] = 15 if aligned_structure else 0
        details["vwap"] = 10 if price_vs_vwap else 0

        if ema_aligned:
            t2 += 10
        if volume_expanding:
            t2 += 10
        rsi_ok = (direction == "BUY" and 50 <= rsi_value <= 75) or (direction == "SELL" and 25 <= rsi_value <= 50)
        if rsi_ok:
            t2 += 10
        candle_ok = (direction == "BUY" and candlestick_pattern in {"HAMMER", "BULLISH_ENGULFING", "MARUBOZU"}) or (direction == "SELL" and candlestick_pattern in {"SHOOTING_STAR", "BEARISH_ENGULFING", "MARUBOZU"})
        if candle_ok:
            # Keep tier total at 30 while still rewarding candle confirmation.
            details["candle_confirmation"] = 5
            if t2 < 30 and t2 + 5 <= 30:
                t2 += 5
        details["ema"] = 10 if ema_aligned else 0
        details["volume"] = 10 if volume_expanding else 0
        details["rsi"] = 10 if rsi_ok else 0

        # Options: 25 points = sentiment, wall headroom, IV, spread, liquidity.
        if pcr is not None:
            bullish_ok = pcr >= 1.10
            bearish_ok = pcr <= 0.90
            if (direction == "BUY" and bullish_ok) or (direction == "SELL" and bearish_ok):
                t3 += 8
            elif 0.90 <= pcr <= 1.10:
                t3 += 4
            details["pcr"] = pcr
        if current_price is not None and call_wall is not None and put_wall is not None:
            wall_distance = (call_wall - current_price) if direction == "BUY" else (current_price - put_wall)
            if wall_distance > 75:
                t3 += 7
            elif wall_distance > 25:
                t3 += 4
            details["wall_headroom_points"] = round(wall_distance, 2)
        if atm_iv is not None:
            if 10.0 <= atm_iv <= 22.0:
                t3 += 4
            elif atm_iv <= 30:
                t3 += 2
            details["atm_iv"] = atm_iv
        if spread_pct is not None:
            if spread_pct <= 0.30:
                t3 += 3
            elif spread_pct <= 0.50:
                t3 += 1
            else:
                penalty += 5
            details["spread_pct"] = spread_pct
        if liquidity_status:
            if liquidity_status.upper() in {"EXCELLENT", "GOOD"}:
                t3 += 3
            elif liquidity_status.upper() == "POOR":
                penalty += 5
            details["liquidity_status"] = liquidity_status
        t3 = min(25, t3)

        if not headroom_available:
            penalty += 15
        if not volatility_tradable:
            penalty += 15
        penalty += max(0, event_penalty)
        details["risk_penalty"] = penalty

        total = max(0, min(100, t1 + t2 + t3 - penalty))
        if total >= 85:
            quality = "VERY_STRONG"
        elif total >= 75:
            quality = "STRONG"
        elif total >= 60:
            quality = "MODERATE"
        elif total >= 45:
            quality = "WEAK"
        else:
            quality = "NO_TRADE"

        return ScoringBreakdown(t1, t2, t3, penalty, total, quality, details)
