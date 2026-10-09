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

from app.data.candle_builder import CandleBuilder
from app.telegram.bot import telegram_notifier

_last_dispatched_signal_id: Optional[str] = None

@router.get("/current", response_model=SignalResponse, summary="Get Current NIFTY Signal")
async def get_current_signal():
    global _last_dispatched_signal_id
    
    # 1. Fetch 1m candles once and resample for all timeframes in memory (Ultra Fast)
    raw_1m = await provider.get_historical_candles(symbol=settings.INSTRUMENT, timeframe="1m", count=200)
    df_1m = pd.DataFrame(raw_1m)
    tf_candles = {}
    if not df_1m.empty:
        df_1m["timestamp"] = pd.to_datetime(df_1m["timestamp"])
        df_1m.set_index("timestamp", inplace=True)
        for tf in settings.TIMEFRAMES:
            if tf == "1m":
                tf_candles["1m"] = df_1m.tail(80)
            else:
                tf_candles[tf] = CandleBuilder.resample_candles(df_1m, tf).tail(80)

    option_snapshot = None
    if settings.UPSTOX_ACCESS_TOKEN:
        option_snapshot = await provider.get_option_chain(symbol=settings.INSTRUMENT)
    elif settings.ENVIRONMENT == "LIVE_DATA":
        raw_option = await provider.get_option_chain(symbol=settings.INSTRUMENT)
        spot_ref = float(tf_candles["5m"]["close"].iloc[-1]) if "5m" in tf_candles and not tf_candles["5m"].empty else 22500.0
        option_snapshot = normalize_groww_option_chain(raw_option, spot_ref)
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

    # 2. Automatically dispatch Telegram alert on new high-probability trade (Score >= 70)
    if result.direction in {"BUY", "SELL", "BUY_CE", "BUY_PE"} and result.score >= 70:
        if _last_dispatched_signal_id != result.signal_id:
            _last_dispatched_signal_id = result.signal_id
            spot_p = float(tf_candles["5m"]["close"].iloc[-1]) if "5m" in tf_candles and not tf_candles["5m"].empty else result.entry_price or 22500.0
            pcr_p = float(option_snapshot.get("pcr", {}).get("oi_pcr", 1.0)) if option_snapshot else 1.0
            await telegram_notifier.send_signal_alert({
                "direction": result.direction,
                "score": result.score,
                "quality": result.quality,
                "market_regime": result.market_regime,
                "signal_id": result.signal_id,
                "entry_price": result.entry_price,
                "stop_loss": result.stop_loss,
                "target_1": result.target_1,
                "target_2": result.target_2,
                "spot_price": spot_p,
                "pcr": pcr_p,
                "option_symbol": f"NIFTY {round(spot_p / 50) * 50} {'CE' if result.direction == 'BUY' else 'PE'}",
                "option_entry": getattr(result, "option_entry", 120.0),
                "option_sl": getattr(result, "option_sl", 90.0),
                "option_target": getattr(result, "option_target", 160.0),
                "delta": getattr(result, "delta", 0.58),
                "theta": getattr(result, "theta", 14.0),
                "reasons": result.reasons
            })

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
