"""
Key Support and Resistance Level Calculator for NIFTY & Indian Indices.
- Extracts genuine Previous Day High (PDH), Low (PDL), and Close (PDC) from prior trading session.
- Computes 15-Minute Opening Range High (ORH) and Low (ORL).
- Identifies dynamic intraday swing pivots (Swing Highs and Swing Lows).
- Evaluates Proximity & Headroom validation to prevent buying into overhead resistance or selling into floors.
"""

from dataclasses import dataclass
from typing import Optional, List
import pandas as pd


@dataclass
class KeyLevelsSnapshot:
    pdh: float  # Previous Day High
    pdl: float  # Previous Day Low
    pdc: float  # Previous Day Close
    is_pd_verified: bool  # True if calculated from genuine previous session data
    day_open: float
    orh: float  # Opening Range High (First 15m)
    orl: float  # Opening Range Low (First 15m)
    nearest_resistance: float
    nearest_support: float
    distance_to_resistance_pts: float
    distance_to_support_pts: float
    has_headroom_for_buy: bool  # Resistance >= min headroom away
    has_headroom_for_sell: bool  # Support >= min headroom away
    swing_highs: List[float]
    swing_lows: List[float]


class KeyLevelsEngine:
    """
    Point-in-time Key Support and Resistance Calculator:
    - Extracts actual prior-day OHLC from multi-day candlestick history without data leakage.
    - Uses local swing extrema for dynamic S/R when multi-day history is unavailable.
    - Prevents false heuristic offsets (+20/-20).
    """

    @classmethod
    def extract_prior_session_ohlc(cls, df: pd.DataFrame) -> Optional[dict]:
        """Extracts genuine previous completed session OHLC by grouping by date."""
        if df.empty:
            return None

        # Check if index or column contains datetime
        dt_series = df.index if isinstance(df.index, pd.DatetimeIndex) else pd.to_datetime(df.get("timestamp", df.get("datetime", pd.Series())))
        if dt_series.empty or not isinstance(dt_series, pd.DatetimeIndex) and dt_series.isnull().all():
            return None

        df_temp = df.copy()
        df_temp["_date"] = dt_series.date if isinstance(dt_series, pd.DatetimeIndex) else dt_series.dt.date
        unique_dates = df_temp["_date"].dropna().unique()

        if len(unique_dates) >= 2:
            prev_date = unique_dates[-2]
            prev_df = df_temp[df_temp["_date"] == prev_date]
            return {
                "pdh": float(prev_df["high"].max()),
                "pdl": float(prev_df["low"].min()),
                "pdc": float(prev_df["close"].iloc[-1]),
                "pdo": float(prev_df["open"].iloc[0])
            }
        return None

    @classmethod
    def calculate_swing_pivots(cls, df: pd.DataFrame, window: int = 5) -> tuple[List[float], List[float]]:
        """Identifies local swing highs and lows for dynamic intraday S/R levels."""
        if len(df) < window * 2 + 1:
            return [], []

        highs = df["high"].values
        lows = df["low"].values
        swing_highs = []
        swing_lows = []

        for i in range(window, len(df) - window):
            current_high = highs[i]
            current_low = lows[i]

            if current_high == max(highs[i - window : i + window + 1]):
                swing_highs.append(round(float(current_high), 2))
            if current_low == min(lows[i - window : i + window + 1]):
                swing_lows.append(round(float(current_low), 2))

        return swing_highs[-5:], swing_lows[-5:]

    @classmethod
    def calculate(
        cls,
        current_price: float,
        df_intraday: pd.DataFrame,
        pdh: Optional[float] = None,
        pdl: Optional[float] = None,
        pdc: Optional[float] = None,
        min_headroom_pts: float = 25.0
    ) -> KeyLevelsSnapshot:
        day_open = float(df_intraday["open"].iloc[0]) if len(df_intraday) > 0 else current_price

        # 15-minute Opening Range (First 3 x 5m or 15 x 1m candles)
        or_candles = df_intraday.iloc[:3] if len(df_intraday) >= 3 else df_intraday
        orh = float(or_candles["high"].max())
        orl = float(or_candles["low"].min())

        # Determine true prior session levels
        is_pd_verified = False
        _pdh, _pdl, _pdc = pdh, pdl, pdc

        if _pdh is None or _pdl is None or _pdc is None:
            prior_session = cls.extract_prior_session_ohlc(df_intraday)
            if prior_session:
                _pdh = _pdh or prior_session["pdh"]
                _pdl = _pdl or prior_session["pdl"]
                _pdc = _pdc or prior_session["pdc"]
                is_pd_verified = True
            else:
                # Single session without prior day data: Derive from opening range and day session extrema
                _pdh = _pdh or float(df_intraday["high"].max())
                _pdl = _pdl or float(df_intraday["low"].min())
                _pdc = _pdc or day_open
                is_pd_verified = False

        # Compute dynamic swing pivots
        swing_highs, swing_lows = cls.calculate_swing_pivots(df_intraday)

        # Compile all overhead resistances
        all_resistances = [r for r in [_pdh, orh, day_open] + swing_highs if r > current_price]
        nearest_resistance = min(all_resistances) if all_resistances else current_price + 100.0

        # Compile all underlying supports
        all_supports = [s for s in [_pdl, orl, day_open] + swing_lows if s < current_price]
        nearest_support = max(all_supports) if all_supports else current_price - 100.0

        dist_res = nearest_resistance - current_price
        dist_sup = current_price - nearest_support

        return KeyLevelsSnapshot(
            pdh=_pdh,
            pdl=_pdl,
            pdc=_pdc,
            is_pd_verified=is_pd_verified,
            day_open=day_open,
            orh=orh,
            orl=orl,
            nearest_resistance=nearest_resistance,
            nearest_support=nearest_support,
            distance_to_resistance_pts=round(dist_res, 2),
            distance_to_support_pts=round(dist_sup, 2),
            has_headroom_for_buy=(dist_res >= min_headroom_pts),
            has_headroom_for_sell=(dist_sup >= min_headroom_pts),
            swing_highs=swing_highs,
            swing_lows=swing_lows
        )
