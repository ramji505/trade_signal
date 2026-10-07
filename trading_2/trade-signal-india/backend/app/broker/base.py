from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Literal


class BrokerProvider(ABC):
    """
    Abstract interface for Indian Broker Integrations (Groww, Zerodha Kite, Angel One, Dhan, Upstox).
    Defines complete order lifecycle: Auth -> Margin Check -> Order Create -> Status -> Cancel -> Position Reconciliation.
    """

    @abstractmethod
    async def authenticate(self) -> bool:
        """Authenticate session using API credentials and TOTP."""
        pass

    @abstractmethod
    async def get_profile(self) -> Dict[str, Any]:
        """Fetch account balance, margin, and user profile."""
        pass

    @abstractmethod
    async def get_quote(self, symbol: str) -> Dict[str, Any]:
        """Get live LTP, bid, ask, and volume quote."""
        pass

    @abstractmethod
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
        """Place an order with broker and return order response with order_id."""
        pass

    @abstractmethod
    async def modify_order(
        self,
        order_id: str,
        price: Optional[float] = None,
        quantity: Optional[int] = None,
        trigger_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """Modify an existing open limit or stop order."""
        pass

    @abstractmethod
    async def cancel_order(self, order_id: str) -> Dict[str, Any]:
        """Cancel an open order."""
        pass

    @abstractmethod
    async def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """Retrieve real-time order status, filled quantity, and average execution price."""
        pass

    @abstractmethod
    async def get_positions(self) -> List[Dict[str, Any]]:
        """Retrieve all active open and closed derivative positions."""
        pass

