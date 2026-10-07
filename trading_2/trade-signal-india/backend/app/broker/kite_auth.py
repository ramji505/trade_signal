"""Zerodha Kite Connect Broker Provider Implementation."""
import httpx
from typing import Dict, Any, Optional, List, Literal
from app.broker.base import BrokerProvider
from app.core.config import settings
from app.core.logging import logger


class KiteConnectProvider(BrokerProvider):
    """Zerodha Kite Connect API v3 Integration."""

    def __init__(self, api_key: Optional[str] = None, access_token: Optional[str] = None):
        self.api_key = api_key or settings.BROKER_API_KEY
        self.access_token = access_token
        self.base_url = "https://api.kite.trade"

    async def authenticate(self) -> bool:
        return bool(self.access_token)

    async def get_profile(self) -> Dict[str, Any]:
        headers = {"X-Kite-Version": "3", "Authorization": f"token {self.api_key}:{self.access_token}"}
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            res = await client.get(f"{self.base_url}/user/margins", headers=headers)
            res.raise_for_status()
            return res.json().get("data", {})

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        headers = {"X-Kite-Version": "3", "Authorization": f"token {self.api_key}:{self.access_token}"}
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            res = await client.get(f"{self.base_url}/quote?i=NSE:{symbol}", headers=headers)
            res.raise_for_status()
            return res.json().get("data", {})

    async def place_order(
        self,
        symbol: str,
        transaction_type: Literal["BUY", "SELL"],
        quantity: int,
        order_type: Literal["MARKET", "LIMIT", "SL", "SL-M"] = "LIMIT",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: Literal["MIS", "NRML", "CNC"] = "MIS",
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        headers = {"X-Kite-Version": "3", "Authorization": f"token {self.api_key}:{self.access_token}"}
        payload = {
            "tradingsymbol": symbol,
            "exchange": "NFO",
            "transaction_type": transaction_type.upper(),
            "order_type": order_type.upper(),
            "quantity": quantity,
            "product": product.upper(),
            "price": price or 0.0,
            "trigger_price": trigger_price or 0.0,
            "tag": tag or "TRADESIGNAL"
        }
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            res = await client.post(f"{self.base_url}/orders/regular", headers=headers, data=payload)
            res.raise_for_status()
            return res.json().get("data", {})

    async def modify_order(
        self,
        order_id: str,
        price: Optional[float] = None,
        quantity: Optional[int] = None,
        trigger_price: Optional[float] = None
    ) -> Dict[str, Any]:
        headers = {"X-Kite-Version": "3", "Authorization": f"token {self.api_key}:{self.access_token}"}
        payload = {}
        if price is not None:
            payload["price"] = price
        if quantity is not None:
            payload["quantity"] = quantity
        if trigger_price is not None:
            payload["trigger_price"] = trigger_price
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            res = await client.put(f"{self.base_url}/orders/regular/{order_id}", headers=headers, data=payload)
            res.raise_for_status()
            return res.json().get("data", {})

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        headers = {"X-Kite-Version": "3", "Authorization": f"token {self.api_key}:{self.access_token}"}
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            res = await client.delete(f"{self.base_url}/orders/regular/{order_id}", headers=headers)
            res.raise_for_status()
            return res.json().get("data", {})

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        headers = {"X-Kite-Version": "3", "Authorization": f"token {self.api_key}:{self.access_token}"}
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            res = await client.get(f"{self.base_url}/orders/{order_id}", headers=headers)
            res.raise_for_status()
            data = res.json().get("data", [])
            return data[-1] if isinstance(data, list) and data else {"status": "UNKNOWN"}

    async def get_positions(self) -> List[Dict[str, Any]]:
        headers = {"X-Kite-Version": "3", "Authorization": f"token {self.api_key}:{self.access_token}"}
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            res = await client.get(f"{self.base_url}/portfolio/positions", headers=headers)
            res.raise_for_status()
            return res.json().get("data", {}).get("net", [])
