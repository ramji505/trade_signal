import numpy as np
import pandas as pd


class TechnicalIndicators:
    """
    Modular calculation engine for technical indicators:
    - EMA (9, 21, 50)
    - RSI (14)
    - VWAP (Session Intraday)
    - ATR (14)
    - Volatility & Candle Morphology (Body, Range, Wicks)
    """

    @staticmethod
    def calculate_ema(series: pd.Series, period: int) -> pd.Series:
        """Exponential Moving Average."""
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """Relative Strength Index (Wilder's smoothing)."""
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -1 * delta.clip(upper=0)

        avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50.0)

    @staticmethod
    def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Average True Range."""
        high = df['high']
        low = df['low']
        close_prev = df['close'].shift(1)

        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
        return atr.fillna(tr.rolling(period).mean()).bfill()

    @staticmethod
    def calculate_vwap(df: pd.DataFrame) -> pd.Series:
        """Intraday Volume Weighted Average Price."""
        typical_price = (df['high'] + df['low'] + df['close']) / 3.0
        vol = df.get('volume', pd.Series(0, index=df.index)).replace(0, np.nan)
        if vol.dropna().empty:
            return typical_price
        pv = typical_price * df['volume']
        cum_pv = pv.cumsum()
        cum_vol = df['volume'].cumsum().replace(0, np.nan)
        vwap = cum_pv / cum_vol
        return vwap.ffill().bfill().fillna(typical_price)

    @classmethod
    def compute_all(cls, df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes the complete suite of technical indicators on an OHLCV DataFrame.
        Returns a new DataFrame enriched with indicator columns.
        """
        out = df.copy()
        out['ema_9'] = cls.calculate_ema(out['close'], 9)
        out['ema_21'] = cls.calculate_ema(out['close'], 21)
        out['ema_50'] = cls.calculate_ema(out['close'], 50)
        out['rsi_14'] = cls.calculate_rsi(out['close'], 14)
        out['atr_14'] = cls.calculate_atr(out, 14)
        out['vwap'] = cls.calculate_vwap(out)

        # Candle Anatomy
        out['candle_range'] = (out['high'] - out['low']).abs()
        out['candle_body'] = (out['close'] - out['open']).abs()
        out['upper_wick'] = out['high'] - out[['open', 'close']].max(axis=1)
        out['lower_wick'] = out[['open', 'close']].min(axis=1) - out['low']
        out['is_bullish'] = out['close'] >= out['open']

        return out
