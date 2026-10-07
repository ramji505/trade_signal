from dataclasses import dataclass
from typing import Literal, Dict
import pandas as pd


@dataclass
class MultiTimeframeState:
    tf_states: Dict[str, Literal["STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"]]
    overall_regime: Literal["STRONG_BULLISH", "BULLISH", "RANGE", "BEARISH", "STRONG_BEARISH"]
    concordance_score: int  # 0 to 100
    is_aligned_for_buy: bool
    is_aligned_for_sell: bool


class MarketRegimeEngine:
    """
    Multi-Timeframe Hierarchy Engine:
    - 15m: Higher-level Market Direction / Regime
    - 10m: Trend Confirmation
    - 5m: Primary Setup Timeframe
    - 3m: Entry Confirmation
    - 1m: Fine Entry Timing / Momentum
    """

    @staticmethod
    def evaluate_tf(df_tf: pd.DataFrame) -> Literal["STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"]:
        if df_tf.empty or len(df_tf) < 3:
            return "NEUTRAL"

        last = df_tf.iloc[-1]
        close = float(last['close'])
        ema_9 = float(last.get('ema_9', close))
        ema_21 = float(last.get('ema_21', close))
        ema_50 = float(last.get('ema_50', close))
        vwap = float(last.get('vwap', close))
        rsi = float(last.get('rsi_14', 50.0))

        # Bullish points
        bull_score = 0
        if close >= vwap:
            bull_score += 2
        if ema_9 >= ema_21:
            bull_score += 2
        if ema_21 >= ema_50 or close >= ema_21:
            bull_score += 2
        if rsi >= 55:
            bull_score += 2
        elif rsi >= 48:
            bull_score += 1

        # Bearish points
        bear_score = 0
        if close <= vwap:
            bear_score += 2
        if ema_9 <= ema_21:
            bear_score += 2
        if ema_21 <= ema_50 or close <= ema_21:
            bear_score += 2
        if rsi <= 45:
            bear_score += 2
        elif rsi <= 52:
            bear_score += 1

        if bull_score >= 6:
            return "STRONG_BULLISH"
        elif bull_score >= 4:
            return "BULLISH"
        elif bear_score >= 6:
            return "STRONG_BEARISH"
        elif bear_score >= 4:
            return "BEARISH"
        return "NEUTRAL"

    @classmethod
    def analyze_mtf(cls, tf_data: Dict[str, pd.DataFrame]) -> MultiTimeframeState:
        states = {}
        for tf in ["15m", "10m", "5m", "3m", "1m"]:
            if tf in tf_data and not tf_data[tf].empty:
                states[tf] = cls.evaluate_tf(tf_data[tf])
            else:
                states[tf] = "NEUTRAL"

        # Multi-timeframe weighted concordance
        weights = {"15m": 25, "10m": 25, "5m": 25, "3m": 15, "1m": 10}
        bull_weight = 0
        bear_weight = 0

        for tf, state in states.items():
            w = weights.get(tf, 20)
            if state in ["STRONG_BULLISH", "BULLISH"]:
                bull_weight += w
            elif state in ["STRONG_BEARISH", "BEARISH"]:
                bear_weight += w

        if bull_weight >= 60:
            overall = "STRONG_BULLISH" if bull_weight >= 80 else "BULLISH"
        elif bear_weight >= 60:
            overall = "STRONG_BEARISH" if bear_weight >= 80 else "BEARISH"
        else:
            overall = "RANGE"

        return MultiTimeframeState(
            tf_states=states,
            overall_regime=overall,
            concordance_score=max(bull_weight, bear_weight),
            is_aligned_for_buy=(bull_weight >= 55 and states.get("5m") in ["STRONG_BULLISH", "BULLISH"]),
            is_aligned_for_sell=(bear_weight >= 55 and states.get("5m") in ["STRONG_BEARISH", "BEARISH"])
        )
