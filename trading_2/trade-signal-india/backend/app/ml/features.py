from typing import Dict, Any
import pandas as pd


class MLFeatureExtractor:
    """
    Leak-free feature extraction engine for NIFTY setups.
    Extracts features strictly available at signal timestamp $t_0$.
    """

    @staticmethod
    def extract_features(
        df_5m: pd.DataFrame,
        mtf_states: Dict[str, str],
        score: int,
        atr_pct: float
    ) -> Dict[str, Any]:
        last = df_5m.iloc[-1]
        close = float(last['close'])
        vwap = float(last['vwap'])
        ema_9 = float(last['ema_9'])
        ema_21 = float(last['ema_21'])

        return {
            "regime_15m": mtf_states.get("15m", "NEUTRAL"),
            "trend_10m": mtf_states.get("10m", "NEUTRAL"),
            "setup_5m": mtf_states.get("5m", "NEUTRAL"),
            "entry_3m": mtf_states.get("3m", "NEUTRAL"),
            "momentum_1m": mtf_states.get("1m", "NEUTRAL"),
            "vwap_dist_pct": round(((close - vwap) / close) * 100.0, 4),
            "ema9_ema21_dist_pct": round(((ema_9 - ema_21) / close) * 100.0, 4),
            "rsi_14": round(float(last['rsi_14']), 2),
            "rvol": round(float(last.get('rvol', 1.0)), 2),
            "atr_pct": round(atr_pct, 4),
            "signal_score": score
        }
