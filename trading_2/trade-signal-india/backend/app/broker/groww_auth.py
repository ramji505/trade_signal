"""Groww API authentication using the documented access-token endpoint."""
from __future__ import annotations

import hashlib
import time
import base64
import hmac
import struct
from datetime import datetime
from typing import Dict, Any, Optional

import httpx

from app.broker.base import BrokerProvider
from app.core.config import settings
from app.core.logging import logger


class GrowwAuthenticationError(RuntimeError):
    pass


class GrowwAuthenticator(BrokerProvider):
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None, totp_secret: Optional[str] = None):
        self.api_key = api_key or settings.BROKER_API_KEY
        self.api_secret = api_secret or settings.BROKER_API_SECRET
        self.totp_secret = totp_secret or settings.BROKER_TOTP_SECRET
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0.0
        self.is_authenticated: bool = False

    @staticmethod
    def generate_totp(secret: str) -> str:
        if not secret:
            raise GrowwAuthenticationError("TOTP secret is required")
        key = base64.b32decode(secret.upper().replace(" ", ""), casefold=True)
        counter = int(time.time() // 30)
        digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
        offset = digest[-1] & 0x0F
        code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1_000_000
        return f"{code:06d}"

    async def _post_token(self, payload: Dict[str, str]):
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            return await client.post(
                f"{settings.GROWW_API_BASE_URL.rstrip('/')}/v1/token/api/access",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json", "Accept": "application/json"},
                json=payload,
            )

    async def authenticate(self) -> bool:
        if not self.api_key:
            raise GrowwAuthenticationError("BROKER_API_KEY is required")

        mode = settings.BROKER_AUTH_MODE.upper()
        payload: Dict[str, str]
        if mode == "APPROVAL":
            if not self.api_secret:
                raise GrowwAuthenticationError("BROKER_API_SECRET is required for APPROVAL mode")
            timestamp = str(int(time.time()))
            checksum = hashlib.sha256(f"{self.api_secret}{timestamp}".encode()).hexdigest()
            payload = {"key_type": "approval", "checksum": checksum, "timestamp": timestamp}
        else:
            if not self.totp_secret:
                raise GrowwAuthenticationError("BROKER_TOTP_SECRET is required for TOTP mode")
            payload = {"key_type": "totp", "totp": self.generate_totp(self.totp_secret)}

        response = await self._post_token(payload)
        response.raise_for_status()
        body = response.json()
        if body.get("status") == "FAILURE":
            raise GrowwAuthenticationError(body.get("message", "Groww authentication failed"))
        token = body.get("token") or body.get("payload", {}).get("token")
        if not token:
            raise GrowwAuthenticationError("Groww response did not contain an access token")
        self.access_token = token
        expiry = body.get("expiry") or body.get("payload", {}).get("expiry")
        if expiry:
            try:
                self.token_expiry = datetime.fromisoformat(str(expiry).replace("Z", "+00:00")).timestamp()
            except ValueError:
                self.token_expiry = time.time() + 20 * 3600
        else:
            self.token_expiry = time.time() + 20 * 3600
        self.is_authenticated = True
        return True

    async def ensure_authenticated(self) -> str:
        if not self.is_authenticated or time.time() >= self.token_expiry - 60:
            await self.authenticate()
        if not self.access_token:
            raise GrowwAuthenticationError("Access token unavailable")
        return self.access_token

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        token = await self.ensure_authenticated()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "X-API-VERSION": "1.0"}
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(f"{settings.GROWW_API_BASE_URL.rstrip('/')}{path}", headers=headers, params=params)
        if response.status_code == 401:
            self.is_authenticated = False
            token = await self.ensure_authenticated()
            headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.get(f"{settings.GROWW_API_BASE_URL.rstrip('/')}{path}", headers=headers, params=params)
        response.raise_for_status()
        body = response.json()
        if body.get("status") == "FAILURE":
            raise GrowwAuthenticationError(body.get("message", f"Groww request failed: {path}"))
        return body.get("payload", body)

    async def _post(self, path: str, json_data: Dict[str, Any]) -> Dict[str, Any]:
        token = await self.ensure_authenticated()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json", "Content-Type": "application/json", "X-API-VERSION": "1.0"}
        async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(f"{settings.GROWW_API_BASE_URL.rstrip('/')}{path}", headers=headers, json=json_data)
        if response.status_code == 401:
            self.is_authenticated = False
            token = await self.ensure_authenticated()
            headers["Authorization"] = f"Bearer {token}"
            async with httpx.AsyncClient(timeout=settings.BROKER_HTTP_TIMEOUT_SECONDS) as client:
                response = await client.post(f"{settings.GROWW_API_BASE_URL.rstrip('/')}{path}", headers=headers, json=json_data)
        response.raise_for_status()
        body = response.json()
        if body.get("status") == "FAILURE":
            raise GrowwAuthenticationError(body.get("message", f"Groww request failed: {path}"))
        return body.get("payload", body)

    async def get_profile(self) -> Dict[str, Any]:
        return await self._get("/v1/user/detail", {})

    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        return await self._get("/v1/live-data/quote", {"exchange": "NSE", "segment": "CASH", "trading_symbol": symbol})

    async def place_order(
        self,
        symbol: str,
        transaction_type: str,
        quantity: int,
        order_type: str = "LIMIT",
        price: Optional[float] = None,
        trigger_price: Optional[float] = None,
        product: str = "MIS",
        tag: Optional[str] = None,
        order_reference_id: Optional[str] = None
    ) -> Dict[str, Any]:
        payload = {
            "trading_symbol": symbol,
            "exchange": "NSE",
            "segment": "FNO",
            "transaction_type": transaction_type.upper(),
            "order_type": order_type.upper(),
            "quantity": quantity,
            "product": product.upper(),
            "price": price or 0.0,
            "trigger_price": trigger_price or 0.0,
            "tag": tag or "TRADESIGNAL_V3",
            "order_reference_id": order_reference_id or f"REF-{int(time.time() * 1000)}"
        }
        logger.info(f"Submitting Groww order: {payload}")
        try:
            return await self._post("/v1/order/create", payload)
        except Exception:
            return await self._post("/v1/orders/user/place", payload)

    async def modify_order(
        self,
        order_id: str,
        price: Optional[float] = None,
        quantity: Optional[int] = None,
        trigger_price: Optional[float] = None
    ) -> Dict[str, Any]:
        payload = {"order_id": order_id}
        if price is not None:
            payload["price"] = price
        if quantity is not None:
            payload["quantity"] = quantity
        if trigger_price is not None:
            payload["trigger_price"] = trigger_price
        logger.info(f"Modifying Groww order {order_id}: {payload}")
        try:
            return await self._post("/v1/order/modify", payload)
        except Exception:
            return await self._post("/v1/orders/user/modify", payload)

    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        logger.info(f"Cancelling Groww order {order_id}")
        try:
            return await self._post("/v1/order/cancel", {"order_id": order_id})
        except Exception:
            return await self._post("/v1/orders/user/cancel", {"order_id": order_id})

    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        try:
            return await self._get("/v1/order/status", {"order_id": order_id})
        except Exception:
            return await self._get("/v1/orders/user/details", {"order_id": order_id})

    async def get_positions(self) -> list[Dict[str, Any]]:
        try:
            res = await self._get("/v1/positions/user", {})
        except Exception:
            res = await self._get("/v1/position/list", {})
        if isinstance(res, list):
            return res
        return res.get("positions", [])

