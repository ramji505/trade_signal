from typing import NamedTuple
import numpy as np
import pandas as pd


class VolumeProfileResult(NamedTuple):
    rvol: float
    is_expanding: bool
    is_contracting: bool
    is_breakout_confirmed: bool
    divergence: str  # 'BULLISH_DIVERGENCE', 'BEARISH_DIVERGENCE', 'NEUTRAL'
    volume_delta: float
    cum_volume_delta: float
    cvd_aligned_buy: bool
    cvd_aligned_sell: bool


class VolumeAnalysis:
    """
    Advanced volume & order flow analytics:
    - Relative Volume (RVOL) compared to moving average baseline
    - Intra-candle Volume Delta (Aggressive Buyers vs Sellers estimation)
    - Cumulative Volume Delta (CVD) tracking
    - Volume Expansion / Contraction
    - Price-Volume and CVD Divergence detection (institutional absorption)
    - Breakout volume verification (> 1.5x average)
    """

    @staticmethod
    def analyze(df: pd.DataFrame, avg_period: int = 20) -> pd.DataFrame:
        out = df.copy()
        out['avg_volume'] = out['volume'].rolling(window=avg_period, min_periods=5).mean()
        out['rvol'] = out['volume'] / out['avg_volume'].replace(0, np.nan)
        out['rvol'] = out['rvol'].fillna(1.0)

        # Volume Expansion (current volume > 1.25x average)
        out['volume_expansion'] = out['rvol'] >= 1.25
        out['volume_contraction'] = out['rvol'] <= 0.75

        # Breakout volume confirmation (RVOL >= 1.5)
        out['breakout_volume_confirmed'] = out['rvol'] >= 1.5

        # --- Microstructure Volume Delta & CVD Estimation ---
        # High - Low range with epsilon to avoid division by zero
        hl_range = (out['high'] - out['low']).replace(0, 0.01)
        # Buying proportion = (Close - Low) / (High - Low)
        buy_ratio = ((out['close'] - out['low']) / hl_range).clip(0.0, 1.0)
        out['buy_volume'] = out['volume'] * buy_ratio
        out['sell_volume'] = out['volume'] * (1.0 - buy_ratio)
        out['volume_delta'] = out['buy_volume'] - out['sell_volume']
        out['cum_volume_delta'] = out['volume_delta'].cumsum()

        # CVD Momentum & Alignment (3-period slope)
        cvd_slope = out['cum_volume_delta'].diff(3).fillna(0.0)
        out['cvd_aligned_buy'] = cvd_slope > 0
        out['cvd_aligned_sell'] = cvd_slope < 0

        # Price-Volume Divergence:
        # Bearish Divergence: Price making higher high but volume/CVD declining
        # Bullish Divergence: Price making lower low but volume/CVD expanding (selling exhaustion)
        price_diff = out['close'].diff(3)
        vol_diff = out['volume'].diff(3)

        out['vol_divergence'] = 'NEUTRAL'
        out.loc[(price_diff > 0) & ((vol_diff < 0) | (cvd_slope < 0)), 'vol_divergence'] = 'BEARISH_DIVERGENCE'
        out.loc[(price_diff < 0) & ((vol_diff < 0) | (cvd_slope > 0)), 'vol_divergence'] = 'BULLISH_DIVERGENCE'

        return out
