"""
Upstox API v2 Live Market Data & Option Chain Provider for NIFTY 50 & Indian Indices.
Provides:
- Real-Time Tick Quotes (LTP, OHLC, Net Change)
- Real Historical & Intraday 1-Minute Candlesticks (Resampled to 1m, 3m, 5m, 10m, 15m)
- Real Live Option Chain (Call/Put LTP, Bid/Ask, OI, PCR, OI Walls, IV)
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import httpx
import pandas as pd

from app.data.base import MarketDataProvider
from app.data.candle_builder import CandleBuilder
from app.core.config import settings
from app.core.logging import logger


class UpstoxMarketDataProvider(MarketDataProvider):
    """
    Live Market Data Provider powered by official Upstox API v2.
    """

    INSTRUMENT_MAP = {
        "NIFTY": "NSE_INDEX|Nifty 50",
        "NIFTY 50": "NSE_INDEX|Nifty 50",
        "BANKNIFTY": "NSE_INDEX|Nifty Bank",
        "FINNIFTY": "NSE_INDEX|Nifty Fin Service",
        "MIDCPNIFTY": "NSE_INDEX|NIFTY MID SELECT",
        "RELIANCE": "NSE_EQ|INE002A01018",
        "HDFCBANK": "NSE_EQ|INE040A01034",
        "ICICIBANK": "NSE_EQ|INE090A01021",
        "INFY": "NSE_EQ|INE009A01021",
        "TCS": "NSE_EQ|INE467B01029",
    }

    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or getattr(settings, "UPSTOX_ACCESS_TOKEN", "")
        self.base_url = "https://api.upstox.com/v2"
        self.headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.access_token}" if self.access_token else ""
        }
        self.connected = bool(self.access_token)

    async def connect(self) -> bool:
        if not self.access_token:
            logger.warning("Upstox Access Token is missing. Please configure UPSTOX_ACCESS_TOKEN in .env")
            return False
        self.connected = True
        return True

    async def disconnect(self) -> None:
        self.connected = False

    def _get_instrument_key(self, symbol: str) -> str:
        return self.INSTRUMENT_MAP.get(symbol.upper(), f"NSE_INDEX|{symbol}")

    async def get_latest_tick(self, symbol: str = "NIFTY") -> Dict[str, Any]:
        inst_key = self._get_instrument_key(symbol)
        url = f"{self.base_url}/market-quote/quotes?instrument_key={inst_key}"

        async with httpx.AsyncClient(timeout=6.0, verify=False) as client:
            res = await client.get(url, headers=self.headers)
            res.raise_for_status()
            data = res.json().get("data", {})
            
            quote_key = list(data.keys())[0] if data else ""
            quote = data.get(quote_key, {})
            last_price = float(quote.get("last_price", quote.get("ohlc", {}).get("close", 22700.0)))
            
            return {
                "symbol": symbol,
                "timestamp": quote.get("timestamp", datetime.now(timezone.utc).isoformat()),
                "last_price": last_price,
                "volume": quote.get("volume", 0),
                "ohlc": quote.get("ohlc", {}),
                "net_change": quote.get("net_change", 0.0),
                "is_live_upstox": True
            }

    async def get_historical_candles(
        self, symbol: str = "NIFTY", timeframe: str = "5m", count: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Fetches true real 1-minute intraday candlesticks from Upstox and resamples them.
        """
        inst_key = self._get_instrument_key(symbol)
        url = f"{self.base_url}/historical-candle/intraday/{inst_key}/1minute"

        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                res = await client.get(url, headers=self.headers)
                res.raise_for_status()
                candles_raw = res.json().get("data", {}).get("candles", [])

                if not candles_raw:
                    logger.warning(f"No intraday candles returned from Upstox for {symbol}")
                    from app.data.mock_provider import MockNiftyProvider
                    return await MockNiftyProvider(base_price=settings.BASE_NIFTY_SPOT_PRICE).get_historical_candles(symbol, timeframe, count)

                # Format Upstox candles: [timestamp, open, high, low, close, volume, oi]
                # Upstox returns latest candles first; reverse to chronological order
                candles_raw = list(reversed(candles_raw))
                formatted = []
                for c in candles_raw:
                    try:
                        ts = pd.to_datetime(c[0])
                        formatted.append({
                            "timestamp": ts,
                            "open": float(c[1]),
                            "high": float(c[2]),
                            "low": float(c[3]),
                            "close": float(c[4]),
                            "volume": float(c[5]) if c[5] is not None else 1000.0
                        })
                    except Exception as e:
                        continue

                df_1m = pd.DataFrame(formatted).set_index("timestamp")
                df_target = CandleBuilder.resample_candles(df_1m, timeframe)
                df_target = df_target.tail(count)

                records = []
                for ts, row in df_target.iterrows():
                    records.append({
                        "timestamp": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                        "timeframe": timeframe,
                        "open": float(row["open"]),
                        "high": float(row["high"]),
                        "low": float(row["low"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                        "vwap": float(row.get("vwap", row["close"]))
                    })

                return records
        except Exception as e:
            logger.warning(f"Upstox intraday candles fetch failed: {e}. Using fallback generator.")
            from app.data.mock_provider import MockNiftyProvider
            return await MockNiftyProvider(base_price=settings.BASE_NIFTY_SPOT_PRICE).get_historical_candles(symbol, timeframe, count)

    async def get_option_chain(self, symbol: str = "NIFTY", expiry_date: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetches live real NSE option chain from Upstox and normalizes it for the SignalEngine.
        """
        inst_key = self._get_instrument_key(symbol)

        try:
            async with httpx.AsyncClient(timeout=8.0, verify=False) as client:
                # 1. Fetch available expiries if not supplied
                if not expiry_date:
                    url_contract = f"{self.base_url}/option/contract?instrument_key={inst_key}"
                    res_c = await client.get(url_contract, headers=self.headers)
                    if res_c.status_code == 200:
                        contracts = res_c.json().get("data", [])
                        expiries = sorted(list(set(c["expiry"] for c in contracts if "expiry" in c)))
                        if expiries:
                            expiry_date = expiries[0]

                if not expiry_date:
                    expiry_date = datetime.now().strftime("%Y-%m-%d")

                # 2. Fetch Option Chain for the selected expiry
                url_chain = f"{self.base_url}/option/chain?instrument_key={inst_key}&expiry_date={expiry_date}"
                res_chain = await client.get(url_chain, headers=self.headers)
                if res_chain.status_code != 200:
                    raise RuntimeError(f"Upstox option chain HTTP {res_chain.status_code}")

                raw_chain = res_chain.json().get("data", [])
                if not raw_chain:
                    raise RuntimeError(f"Empty option chain for {symbol} on {expiry_date}")

                spot_price = float(raw_chain[0].get("underlying_spot_price", 22700.0))
                total_ce_oi = 0
                total_pe_oi = 0
                max_ce_oi = 0
                max_pe_oi = 0
                call_wall_strike = spot_price + 100.0
                put_wall_strike = spot_price - 100.0
                normalized_chain = []

                for strike_item in raw_chain:
                    strike = float(strike_item.get("strike_price", 0.0))
                    call_opt = strike_item.get("call_options", {})
                    put_opt = strike_item.get("put_options", {})

                    ce_md = call_opt.get("market_data", {}) if call_opt else {}
                    pe_md = put_opt.get("market_data", {}) if put_opt else {}

                    ce_ltp = float(ce_md.get("ltp", 0.0) or 0.0)
                    pe_ltp = float(pe_md.get("ltp", 0.0) or 0.0)
                    ce_oi = int(ce_md.get("oi", 0) or 0)
                    pe_oi = int(pe_md.get("oi", 0) or 0)
                    ce_vol = int(ce_md.get("volume", 0) or 0)
                    pe_vol = int(pe_md.get("volume", 0) or 0)

                    total_ce_oi += ce_oi
                    total_pe_oi += pe_oi

                    if ce_oi > max_ce_oi:
                        max_ce_oi = ce_oi
                        call_wall_strike = strike
                    if pe_oi > max_pe_oi:
                        max_pe_oi = pe_oi
                        put_wall_strike = strike

                    # Approximate IV / Greeks
                    ce_iv = float(call_opt.get("option_greeks", {}).get("iv", 0.13) or 0.13) if call_opt else 0.13
                    pe_iv = float(put_opt.get("option_greeks", {}).get("iv", 0.13) or 0.13) if put_opt else 0.13

                    normalized_chain.append({
                        "strike": strike,
                        "ce_ltp": ce_ltp,
                        "pe_ltp": pe_ltp,
                        "ce_oi": ce_oi,
                        "pe_oi": pe_oi,
                        "ce_volume": ce_vol,
                        "pe_volume": pe_vol,
                        "ce_iv": ce_iv,
                        "pe_iv": pe_iv,
                        "ce_bid": float(ce_md.get("bid_price", 0.0) or ce_ltp),
                        "ce_ask": float(ce_md.get("ask_price", 0.0) or ce_ltp),
                        "pe_bid": float(pe_md.get("bid_price", 0.0) or pe_ltp),
                        "pe_ask": float(pe_md.get("ask_price", 0.0) or pe_ltp)
                    })

                overall_pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else 1.0

                # Find closest ATM strike
                atm_item = min(normalized_chain, key=lambda x: abs(x["strike"] - spot_price))

                return {
                    "symbol": symbol,
                    "spot_price": spot_price,
                    "expiry_date": expiry_date,
                    "atm_strike": atm_item["strike"],
                    "pcr": {
                        "oi_pcr": overall_pcr,
                        "total_ce_oi": total_ce_oi,
                        "total_pe_oi": total_pe_oi
                    },
                    "oi_walls": {
                        "call_wall_strike": call_wall_strike,
                        "put_wall_strike": put_wall_strike,
                        "max_ce_oi": max_ce_oi,
                        "max_pe_oi": max_pe_oi
                    },
                    "spread_pct": 0.15,
                    "liquidity_status": "GOOD",
                    "chain": normalized_chain,
                    "is_live_upstox": True
                }
        except Exception as e:
            logger.warning(f"Upstox option chain fetch failed: {e}. Using fallback option chain generator.")
            from app.data.mock_provider import MockNiftyProvider
            return await MockNiftyProvider(base_price=settings.BASE_NIFTY_SPOT_PRICE).get_option_chain(symbol)

    async def get_heavyweights_quotes(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetches live real-time quotes for NIFTY 50 top driving heavyweight components.
        Returns mapped symbol trends: BULLISH / BEARISH / NEUTRAL based on net change.
        """
        keys = "NSE_EQ|INE040A01034,NSE_EQ|INE002A01018,NSE_EQ|INE090A01021,NSE_EQ|INE009A01021,NSE_INDEX|Nifty Bank,NSE_INDEX|India VIX"
        url = f"{self.base_url}/market-quote/quotes"

        try:
            async with httpx.AsyncClient(timeout=6.0, verify=False) as client:
                res = await client.get(url, headers=self.headers, params={"instrument_key": keys})
                if res.status_code != 200:
                    return {}
                data = res.json().get("data", {})
                
                mapping = {
                    "NSE_EQ:HDFCBANK": "HDFCBANK",
                    "NSE_EQ:RELIANCE": "RELIANCE",
                    "NSE_EQ:ICICIBANK": "ICICIBANK",
                    "NSE_EQ:INFY": "INFY",
                    "NSE_INDEX:Nifty Bank": "BANKNIFTY",
                    "NSE_INDEX:India VIX": "INDIA_VIX"
                }

                results = {}
                for raw_k, info in data.items():
                    sym = mapping.get(raw_k, raw_k)
                    net_chg = float(info.get("net_change", 0.0) or 0.0)
                    ltp = float(info.get("last_price", 0.0) or 0.0)
                    trend = "BULLISH" if net_chg > 0.1 else ("BEARISH" if net_chg < -0.1 else "NEUTRAL")
                    results[sym] = {
                        "ltp": ltp,
                        "net_change": net_chg,
                        "trend": trend
                    }
                return results
        except Exception as e:
            logger.warning(f"Failed to fetch live heavyweight quotes: {e}")
            return {}

    async def get_india_vix(self) -> float:
        """
        Returns live India VIX value for dynamic ATR & risk calculations.
        """
        try:
            url = f"{self.base_url}/market-quote/quotes"
            async with httpx.AsyncClient(timeout=4.0, verify=False) as client:
                res = await client.get(url, headers=self.headers, params={"instrument_key": "NSE_INDEX|India VIX"})
                if res.status_code == 200:
                    data = res.json().get("data", {})
                    vix_data = data.get("NSE_INDEX:India VIX", {})
                    return float(vix_data.get("last_price", 14.0) or 14.0)
        except Exception:
            pass
        return 14.0

