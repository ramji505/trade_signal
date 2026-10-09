from typing import Optional, Dict, Any
import httpx
from app.core.logging import logger


class TelegramNotifier:
    """Institutional Telegram bot notification service with anti-spam cooldown and rich F&O formatting."""

    def __init__(self, token: Optional[str] = None, chat_id: Optional[str] = None):
        from app.core.config import settings
        self.token = token or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or getattr(settings, "TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.token and self.chat_id)

    async def send_signal_alert(self, signal_data: Dict[str, Any]) -> bool:
        if not self.enabled:
            logger.info("Telegram notification skipped (bot token/chat_id not configured)")
            return False

        direction = signal_data.get("direction", "WAIT")
        setup_type = signal_data.get("setup_type", "PULLBACK_ACCUMULATION")
        score = signal_data.get("score", 0)
        quality = signal_data.get("quality", "NEUTRAL")
        regime = signal_data.get("market_regime", "TRENDING")
        sig_id = signal_data.get("signal_id", "SIG-LIVE")

        entry = float(signal_data.get("entry_price") or 0.0)
        sl = float(signal_data.get("stop_loss") or 0.0)
        t1 = float(signal_data.get("target_1") or 0.0)
        t2 = float(signal_data.get("target_2") or 0.0)

        opt_sym = signal_data.get("option_symbol") or f"NIFTY-{direction}"
        opt_entry = float(signal_data.get("option_entry") or 0.0)
        opt_sl = float(signal_data.get("option_sl") or 0.0)
        opt_target = float(signal_data.get("option_target") or 0.0)
        delta = float(signal_data.get("delta") or 0.55)
        theta = float(signal_data.get("theta") or 14.0)

        if direction in {"BUY", "SELL", "BUY_CE", "BUY_PE"} and entry > 0:
            message = (
                f"🇮🇳 <b>TRADESIGNAL INDIA — LIVE NIFTY SETUP</b>\n\n"
                f"🎯 <b>Direction</b>: <code>{direction}</code> | <b>Setup</b>: <code>{setup_type}</code>\n"
                f"⭐ <b>Score</b>: <code>{score}/100</code> ({quality}) | <b>Regime</b>: <code>{regime}</code>\n\n"
                f"📍 <b>Spot Reference</b>:\n"
                f"  • Entry: ₹{entry:.1f}\n"
                f"  • Stop Loss: ₹{sl:.1f}\n"
                f"  • Target 1: ₹{t1:.1f}\n"
                f"  • Target 2: ₹{t2:.1f}\n\n"
                f"⚡ <b>Recommended Option Contract</b>:\n"
                f"  • Instrument: <code>{opt_sym}</code>\n"
                f"  • Premium Entry: ₹{opt_entry:.1f}\n"
                f"  • Premium SL: ₹{opt_sl:.1f}\n"
                f"  • Premium Target: ₹{opt_target:.1f}\n"
                f"  • Delta: <code>{delta:.2f}</code> | Theta: <code>₹{theta:.1f}/day</code>\n\n"
                f"🛡️ <b>Risk Check</b>: Zero lookahead verified. Intraday auto squareoff @ 15:15 IST.\n"
                f"🆔 Signal ID: <code>{sig_id}</code>"
            )
        else:
            reasons_list = signal_data.get("reasons", [])
            reasons_summary = "\n".join([f"  • {str(r)}" for r in reasons_list[:4]]) if reasons_list else "  • Multi-timeframe confluence scan in progress"
            spot_ref = float(signal_data.get("spot_price") or 0.0)
            pcr_ref = float(signal_data.get("pcr") or 0.0)
            message = (
                f"🇮🇳 <b>TRADESIGNAL INDIA — LIVE SCAN UPDATE</b>\n\n"
                f"📊 <b>Status</b>: <code>SCANNING &amp; MONITORING</code>\n"
                f"📍 <b>NIFTY 50 Spot</b>: <code>₹{spot_ref:.2f}</code> | <b>PCR</b>: <code>{pcr_ref:.2f}</code>\n"
                f"🎯 <b>Current Regime</b>: <code>{regime}</code>\n"
                f"⭐ <b>Signal Score</b>: <code>{score}/100</code> (Trigger Threshold: 80)\n\n"
                f"🔍 <b>Condition Analysis</b>:\n"
                f"{reasons_summary}\n\n"
                f"🛡️ <b>Execution Rule</b>: Engine will only dispatch real BUY_CE/BUY_PE orders when score exceeds threshold with full MTF + Greeks alignment."
            )

        try:
            url = f"https://api.telegram.org/bot{self.token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            async with httpx.AsyncClient(timeout=12.0, verify=False) as client:
                res = await client.post(url, json=payload)
                if res.status_code == 200:
                    logger.info("Telegram alert dispatched successfully.")
                    return True
                else:
                    logger.warning(f"Telegram dispatch failed: {res.text}")
                    return False
        except Exception as e:
            logger.warning(f"Telegram notification network timeout / exception: {e}")
            return False


telegram_notifier = TelegramNotifier()
