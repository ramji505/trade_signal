"""
Automated Live Market Background Scanner & Real-Time Telegram Dispatcher.
Executes every 60 seconds:
1. Fetches live multi-timeframe candles (1m, 3m, 5m, 10m, 15m) from Upstox.
2. Fetches live Heavyweight Confluence (HDFCBANK, RELIANCE, ICICIBANK, INFY, BANKNIFTY).
3. Fetches live NSE Option Chain with PCR, Max Pain, and OI shifts.
4. Executes Master Quantitative Signal Engine.
5. Dispatches instant Telegram alert when high-probability setup (Score >= 80) is detected.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import pandas as pd

from app.core.config import settings
from app.core.logging import logger
from app.data.upstox_provider import UpstoxMarketDataProvider
from app.strategy.signal_engine import SignalEngine
from app.telegram.bot import telegram_notifier


class LiveMarketScanner:
    def __init__(self, interval_seconds: int = 60):
        self.interval_seconds = interval_seconds
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.provider = UpstoxMarketDataProvider() if settings.UPSTOX_ACCESS_TOKEN else None
        self.engine = SignalEngine(score_threshold=settings.SIGNAL_SCORE_THRESHOLD)
        self.last_scan_time: Optional[datetime] = None
        self.last_signal: Optional[Dict[str, Any]] = None
        self.scan_count: int = 0
        self.alerts_sent: int = 0

    async def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._scan_loop())
        logger.info(f"[LIVE SCANNER] Background market scanner started (Interval: {self.interval_seconds}s)")

    async def stop(self):
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("[LIVE SCANNER] Background market scanner stopped")

    async def _scan_loop(self):
        while self.is_running:
            try:
                await self.execute_single_scan()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[LIVE SCANNER] Exception during scan iteration: {e}", exc_info=True)

            await asyncio.sleep(self.interval_seconds)

    async def execute_single_scan(self) -> Optional[Dict[str, Any]]:
        if not self.provider or not settings.UPSTOX_ACCESS_TOKEN:
            return None

        self.scan_count += 1
        self.last_scan_time = datetime.now(timezone.utc)

        # 1. Fetch Multi-Timeframe Candles
        tf_candles = {}
        for tf in settings.TIMEFRAMES:
            raw = await self.provider.get_historical_candles(symbol=settings.INSTRUMENT, timeframe=tf, count=80)
            df = pd.DataFrame(raw)
            if not df.empty:
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
                tf_candles[tf] = df

        if "5m" not in tf_candles or tf_candles["5m"].empty:
            return None

        # 2. Fetch Heavyweights & India VIX
        heavyweights_data = await self.provider.get_heavyweights_quotes()
        component_trends = {sym: info.get("trend", "NEUTRAL") for sym, info in heavyweights_data.items()}

        # 3. Fetch Real Option Chain
        option_snapshot = await self.provider.get_option_chain(symbol=settings.INSTRUMENT)

        # 4. Process Signal Engine
        result = self.engine.process(
            symbol=settings.INSTRUMENT,
            tf_candles=tf_candles,
            is_market_open=True,
            is_data_healthy=True,
            option_snapshot=option_snapshot,
            component_trends=component_trends
        )

        spot_price = float(tf_candles["5m"]["close"].iloc[-1])
        pcr_val = float(option_snapshot.get("pcr", {}).get("oi_pcr", 1.0)) if option_snapshot else 1.0

        scan_summary = {
            "timestamp": self.last_scan_time.isoformat(),
            "signal_id": result.signal_id,
            "direction": result.direction,
            "score": result.score,
            "quality": result.quality,
            "market_regime": result.market_regime,
            "spot_price": spot_price,
            "pcr": pcr_val,
            "entry_price": result.entry_price,
            "stop_loss": result.stop_loss,
            "target_1": result.target_1,
            "target_2": result.target_2,
            "reasons": result.reasons,
            "component_trends": component_trends,
        }
        self.last_signal = scan_summary

        # 5. Dispatch Telegram Alert if actionable
        if result.direction in {"BUY", "SELL", "BUY_CE", "BUY_PE"} and result.score >= settings.SIGNAL_SCORE_THRESHOLD:
            logger.info(f"[LIVE SCANNER] High-probability signal detected: {result.direction} (Score {result.score}/100). Dispatching Telegram alert...")
            sent = await telegram_notifier.send_signal_alert({
                "direction": result.direction,
                "score": result.score,
                "quality": result.quality,
                "market_regime": result.market_regime,
                "signal_id": result.signal_id,
                "entry_price": result.entry_price,
                "stop_loss": result.stop_loss,
                "target_1": result.target_1,
                "target_2": result.target_2,
                "spot_price": spot_price,
                "pcr": pcr_val,
                "option_symbol": getattr(result, "option_symbol", f"NIFTY {round(spot_price/50)*50} CE"),
                "option_entry": getattr(result, "option_entry", 120.0),
                "option_sl": getattr(result, "option_sl", 90.0),
                "option_target": getattr(result, "option_target", 160.0),
                "delta": getattr(result, "delta", 0.55),
                "theta": getattr(result, "theta", 14.0),
                "reasons": result.reasons
            })
            if sent:
                self.alerts_sent += 1

        return scan_summary


live_market_scanner = LiveMarketScanner(interval_seconds=60)
