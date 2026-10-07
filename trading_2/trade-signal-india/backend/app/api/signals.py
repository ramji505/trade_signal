from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Literal, Dict, Any
from datetime import datetime
import pandas as pd

from app.core.config import settings
from app.data.mock_provider import MockNiftyProvider
from app.data.groww_provider import GrowwMarketDataProvider
from app.data.upstox_provider import UpstoxMarketDataProvider
from app.options.option_adapter import normalize_groww_option_chain
from app.strategy.signal_engine import SignalEngine

router = APIRouter(prefix="/signals", tags=["Signals"])

def _provider():
    if settings.UPSTOX_ACCESS_TOKEN:
        return UpstoxMarketDataProvider()
    elif settings.ENVIRONMENT == "LIVE_DATA":
        return GrowwMarketDataProvider()
    return MockNiftyProvider(base_price=settings.BASE_NIFTY_SPOT_PRICE)

provider = _provider()
signal_engine = SignalEngine(score_threshold=settings.SIGNAL_SCORE_THRESHOLD)

class ScoringDetailResponse(BaseModel):
    tier1_structure_score: int
    tier2_indicator_score: int
    tier3_options_score: int
    tier4_risk_penalty: int
    total_score: int
    quality: str
    details: Dict[str, Any]

class SignalResponse(BaseModel):
    signal_id: str
    symbol: str
    timestamp: datetime
    direction: Literal["BUY", "SELL", "WAIT"]
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target_1: Optional[float] = None
    target_2: Optional[float] = None
    score: int
    quality: Literal["NO_TRADE", "WEAK", "MODERATE", "STRONG", "VERY_STRONG"]
    market_regime: str
    timeframe_states: Dict[str, str]
    reasons: list[str]
    scoring_breakdown: ScoringDetailResponse
    status: str = "ACTIVE"

@router.get("/current", response_model=SignalResponse, summary="Get Current NIFTY Signal")
async def get_current_signal():
    tf_candles = {}
    for tf in settings.TIMEFRAMES:
        raw = await provider.get_historical_candles(symbol=settings.INSTRUMENT, timeframe=tf, count=80)
        df = pd.DataFrame(raw)
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df.set_index("timestamp", inplace=True)
            tf_candles[tf] = df

    option_snapshot = None
    if settings.UPSTOX_ACCESS_TOKEN:
        option_snapshot = await provider.get_option_chain(symbol=settings.INSTRUMENT)
    elif settings.ENVIRONMENT == "LIVE_DATA":
        # Live provider returns Groww's native option payload; normalize it once at the API boundary.
        raw_option = await provider.get_option_chain(symbol=settings.INSTRUMENT)
        option_snapshot = normalize_groww_option_chain(raw_option, float(tf_candles["5m"]["close"].iloc[-1]))
    else:
        option_snapshot = await provider.get_option_chain(symbol=settings.INSTRUMENT)

    component_trends = None
    if hasattr(provider, "get_heavyweights_quotes"):
        hw_quotes = await provider.get_heavyweights_quotes()
        component_trends = {sym: info.get("trend", "NEUTRAL") for sym, info in hw_quotes.items()}

    result = signal_engine.process(
        symbol=settings.INSTRUMENT,
        tf_candles=tf_candles,
        is_market_open=True,
        is_data_healthy=True,
        option_snapshot=option_snapshot,
        component_trends=component_trends
    )
    b = result.scoring_breakdown
    return SignalResponse(**{
        "signal_id": result.signal_id, "symbol": result.symbol, "timestamp": result.timestamp,
        "direction": result.direction, "entry_price": result.entry_price, "stop_loss": result.stop_loss,
        "target_1": result.target_1, "target_2": result.target_2, "score": result.score,
        "quality": result.quality, "market_regime": result.market_regime, "timeframe_states": result.timeframe_states,
        "reasons": result.reasons,
        "scoring_breakdown": ScoringDetailResponse(
            tier1_structure_score=b.tier1_structure_score, tier2_indicator_score=b.tier2_indicator_score,
            tier3_options_score=b.tier3_options_score, tier4_risk_penalty=b.tier4_risk_penalty,
            total_score=b.total_score, quality=b.quality, details=b.details
        ),
        "status": result.status
    })

@router.get("/scanner/status", summary="Get Live Scanner Status")
async def get_scanner_status():
    from app.services.live_scanner import live_market_scanner
    return {
        "is_running": live_market_scanner.is_running,
        "interval_seconds": live_market_scanner.interval_seconds,
        "scan_count": live_market_scanner.scan_count,
        "alerts_sent": live_market_scanner.alerts_sent,
        "last_scan_time": live_market_scanner.last_scan_time.isoformat() if live_market_scanner.last_scan_time else None,
        "last_signal": live_market_scanner.last_signal
    }

@router.post("/scanner/start", summary="Start Live Background Scanner")
async def start_scanner():
    from app.services.live_scanner import live_market_scanner
    await live_market_scanner.start()
    return {"status": "started", "interval_seconds": live_market_scanner.interval_seconds}

@router.post("/scanner/stop", summary="Stop Live Background Scanner")
async def stop_scanner():
    from app.services.live_scanner import live_market_scanner
    await live_market_scanner.stop()
    return {"status": "stopped"}

@router.get("/history", summary="Get Historical Signals")
async def get_signal_history():
    return {"signals": [], "total": 0, "message": "Continuous live paper signals audit log"}
