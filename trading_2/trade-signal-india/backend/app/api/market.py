from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Literal, List, Optional
import pandas as pd
from datetime import datetime

from app.data.mock_provider import MockNiftyProvider
from app.data.groww_provider import GrowwMarketDataProvider
from app.data.upstox_provider import UpstoxMarketDataProvider
from app.core.config import settings
from app.indicators.technical import TechnicalIndicators

router = APIRouter(prefix="/market", tags=["Market Data"])
provider = UpstoxMarketDataProvider() if settings.UPSTOX_ACCESS_TOKEN else (GrowwMarketDataProvider() if settings.ENVIRONMENT == "LIVE_DATA" else MockNiftyProvider(base_price=settings.BASE_NIFTY_SPOT_PRICE))


class MarketStatusResponse(BaseModel):
    status: Literal["OPEN", "CLOSED", "PRE_OPEN", "POST_CLOSE"]
    data_quality: Literal["HEALTHY", "STALE", "DISCONNECTED"]
    is_mock: bool
    instrument: str


class CandlePoint(BaseModel):
    time: int  # UNIX timestamp (seconds)
    open: float
    high: float
    low: float
    close: float
    volume: float


class IndicatorPoint(BaseModel):
    time: int
    value: float


class ChartDataResponse(BaseModel):
    symbol: str
    timeframe: str
    candles: List[CandlePoint]
    ema_9: List[IndicatorPoint]
    ema_21: List[IndicatorPoint]
    ema_50: List[IndicatorPoint]
    vwap: List[IndicatorPoint]
    last_price: float


@router.get("/status", response_model=MarketStatusResponse, summary="Get Market Status")
async def get_market_status():
    """Returns current market session status and data feed health."""
    return MarketStatusResponse(
        status="OPEN",
        data_quality="HEALTHY",
        is_mock=(settings.ENVIRONMENT != "LIVE_DATA"),
        instrument=settings.INSTRUMENT
    )


@router.get("/candles", response_model=ChartDataResponse, summary="Get Enriched Chart Candles")
async def get_chart_candles(
    symbol: str = settings.INSTRUMENT,
    timeframe: str = Query("5m", pattern="^(1m|3m|5m|10m|15m)$"),
    count: int = Query(80, ge=20, le=300)
):
    """Returns historical candles enriched with EMA 9/21/50 and VWAP formatted for TradingView Lightweight Charts."""
    raw = await provider.get_historical_candles(symbol=symbol, timeframe=timeframe, count=count)
    df = pd.DataFrame(raw)
    if df.empty:
        return ChartDataResponse(
            symbol=symbol,
            timeframe=timeframe,
            candles=[],
            ema_9=[],
            ema_21=[],
            ema_50=[],
            vwap=[],
            last_price=0.0
        )

    df["dt"] = pd.to_datetime(df["timestamp"])
    df.set_index("dt", inplace=True)
    df_enriched = TechnicalIndicators.compute_all(df)

    candles = []
    ema9_pts = []
    ema21_pts = []
    ema50_pts = []
    vwap_pts = []

    for dt, row in df_enriched.iterrows():
        # Convert timestamp to unix seconds (TradingView standard)
        unix_ts = int(dt.timestamp())
        candles.append(CandlePoint(
            time=unix_ts,
            open=round(float(row["open"]), 2),
            high=round(float(row["high"]), 2),
            low=round(float(row["low"]), 2),
            close=round(float(row["close"]), 2),
            volume=round(float(row["volume"]), 2)
        ))

        if pd.notna(row.get("ema_9")):
            ema9_pts.append(IndicatorPoint(time=unix_ts, value=round(float(row["ema_9"]), 2)))
        if pd.notna(row.get("ema_21")):
            ema21_pts.append(IndicatorPoint(time=unix_ts, value=round(float(row["ema_21"]), 2)))
        if pd.notna(row.get("ema_50")):
            ema50_pts.append(IndicatorPoint(time=unix_ts, value=round(float(row["ema_50"]), 2)))
        if pd.notna(row.get("vwap")):
            vwap_pts.append(IndicatorPoint(time=unix_ts, value=round(float(row["vwap"]), 2)))

    last_p = round(float(df_enriched["close"].iloc[-1]), 2)

    return ChartDataResponse(
        symbol=symbol,
        timeframe=timeframe,
        candles=candles,
        ema_9=ema9_pts,
        ema_21=ema21_pts,
        ema_50=ema50_pts,
        vwap=vwap_pts,
        last_price=last_p
    )
