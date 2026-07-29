"""
PolyClient - Wrapper for Polymarket CLOB Client (py-clob-client-v2).

Notes on the v1 -> v2 migration:
- Module is now `py_clob_client_v2` (alongside the legacy `py_clob_client`).
- `OrderArgs`/`MarketOrderArgs` are aliases for the V2 dataclasses; both still
  accept BUY/SELL strings or the new `Side` enum, so we keep using strings.
- `client.create_or_derive_api_creds()` was renamed to
  `client.create_or_derive_api_key()`.

- Single-order cancel changed from `client.cancel(order_id)` to
  `client.cancel_order(OrderPayload(orderID=...))`. We still accept a plain
  string at the wrapper boundary so callers don't have to change.
- Listing orders is now `client.get_open_orders(params)` (was `get_orders`).
- `OrderType.IOC` no longer exists; valid order types are GTC/FOK/GTD/FAK.
"""
import logging
import time
from typing import Optional, Dict, Any, List

try:
    from py_clob_client_v2.clob_types import (
        OrderType,
        OrderArgs,
        MarketOrderArgs,
        PostOrdersV2Args,
        PartialCreateOrderOptions,
        OpenOrderParams,
        OrderPayload,
    )
    from py_clob_client_v2.client import ClobClient
    from py_clob_client_v2.constants import POLYGON, ZERO_ADDRESS
    try:
        from py_clob_client_v2.exceptions import PolyApiException
    except ImportError:
        PolyApiException = Exception  # type: ignore
    BUY = "BUY"
    SELL = "SELL"
    CLOB_AVAILABLE = True
except ImportError:
    ClobClient = None  # type: ignore
    POLYGON = 137
    ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
    OrderArgs = None  # type: ignore
    MarketOrderArgs = None  # type: ignore
    OrderType = None  # type: ignore
    BUY = "BUY"  # type: ignore
    SELL = "SELL"  # type: ignore
    PostOrdersArgs = None  # type: ignore
    PartialCreateOrderOptions = None  # type: ignore
    OpenOrderParams = None  # type: ignore
    OrderPayload = None  # type: ignore
    PolyApiException = Exception  # type: ignore
    CLOB_AVAILABLE = False


class PolyClient:
    """
    Client wrapper for Polymarket CLOB API (V2).

    This class provides a simplified interface to interact with the Polymarket
    CLOB (Central Limit Order Book) API for placing and managing orders.
    """

    def __init__(
        self,
        private_key: str,
        host: str,
        chain_id: int,
        signature_type: int,
        funder: Optional[str] = None,
    ):
        """
        Initialize PolyClient.

        Args:
            private_key: Private key for signing transactions.
            host: CLOB API host URL (e.g., "https://clob.polymarket.com").
            chain_id: Blockchain chain ID (e.g., 137 for Polygon).
            signature_type: Signature type for orders (SignatureTypeV2 int).
            funder: Optional funder address.
        """
        self.private_key = private_key
        self.host = host
        self.chain_id = chain_id
        self.signature_type = signature_type
        self.funder = funder

        if CLOB_AVAILABLE and ClobClient is not None:
            self.client = ClobClient(
                self.host,
                key=self.private_key,
                chain_id=self.chain_id,
                signature_type=self.signature_type,
                funder=self.funder,
            )
            # V2 renamed create_or_derive_api_creds -> create_or_derive_api_key.
            # The library always tries POST /auth/api-key first and falls back to
            # derive when it fails (400 "Could not create api key" if a key already
            # exists). The HTTP helper logs that 400 at ERROR level even though it
            # is expected, so silence that specific logger only for the bootstrap.


            _http_logger = logging.getLogger("py_clob_client_v2.http_helpers.helpers")
            _prev_level = _http_logger.level
            _http_logger.setLevel(logging.CRITICAL)
            try:
                self.client_creds = self.client.create_or_derive_api_key()
            finally:
                _http_logger.setLevel(_prev_level)
            self.client.set_api_creds(self.client_creds)
        else:
            self.client = None
            self.client_creds = None
            if not CLOB_AVAILABLE:
                print("Warning: py-clob-client-v2 not installed. Install with: pip install py-clob-client-v2")

    def is_available(self) -> bool:
        """Check if CLOB client is available and initialized."""
        return self.client is not None

    def get_api_creds(self) -> Optional[Dict[str, str]]:
        """
        Get CLOB API credentials for user WebSocket auth.
        Returns a plain dict with apiKey/secret/passphrase (from the ApiCreds object).
        """
        c = self.client_creds
        if c is None:
            return None
        if isinstance(c, dict):
            return c
        return {
            "apiKey": getattr(c, "api_key", None),
            "secret": getattr(c, "api_secret", None),
            "passphrase": getattr(c, "api_passphrase", None),
        }

    @staticmethod
    def _log_order_error(e: Exception, prefix: str = "Error placing order") -> None:
        """Log exception and underlying cause (e.g. connection/timeout)."""
        print(f"{prefix}: {e}")
        cause = getattr(e, "__cause__", None)
        if cause is not None and str(cause) != str(e):
            print(f"  cause: {cause}")
        if "Request exception" in str(e):
            print("  tip: Often network/timeout. Check CLOB_API_HOST, firewall, and try again.")

    def place_limit_order(
        self,
        token_id: str,
        side: str,
        price: float,
        size: float,
        order_type: Optional[str] = None,
    ) -> Optional[Dict[Any, Any]]:
        """
        Place a limit order on Polymarket CLOB.

        Args:
            token_id: The token ID to trade.
            side: "BUY" or "SELL".
            price: Price per share (0.0 to 1.0).
            size: Size of the order.
            order_type: Order type string (default: GTC). Valid: GTC/FOK/GTD/FAK.

        Returns:
            Order response dictionary or None if failed.
        """
        if not self.client:
            print("Error: CLOB client not initialized.")
            return None

        if not CLOB_AVAILABLE or OrderArgs is None or OrderType is None:
            print("Error: py-clob-client-v2 not available.")
            return None

        if side.upper() not in ["BUY", "SELL"]:
            print(f"Error: Invalid side '{side}'. Must be 'BUY' or 'SELL'")
            return None

        order_type = order_type or OrderType.GTC
        order = OrderArgs(
                    token_id=token_id,
                    price=float(price),
                    size=float(size),
                    side=BUY if side.upper() == "BUY" else SELL,
                )
        signed = self.client.create_order(order)
        resp = self.client.post_order(signed, order_type)
        return resp

    def place_multiple_limit_orders(self, orders: list[dict[Any, Any]]) -> Optional[Dict[Any, Any]]:
        """
        Place multiple limit orders on Polymarket CLOB.

        Args:
            orders: List of order dictionaries with keys: token_id, side, price, size.

        Returns:
            Order response dictionary or None if failed.
        """
        if not self.client:
            print("Error: CLOB client not initialized.")
            return None

        if (
            not CLOB_AVAILABLE
            or OrderArgs is None
            or PostOrdersV2Args is None
            or PartialCreateOrderOptions is None
            or OrderType is None
        ):
            print("Error: py-clob-client-v2 not available.")
            return None

        options = PartialCreateOrderOptions(tick_size="0.01", neg_risk=False)
        args_list = []
        for o in orders:
            order_args = OrderArgs(
                token_id=o["token_id"],
                price=float(o["price"]),
                size=float(o["size"]),
                side=BUY if str(o["side"]).upper() == "BUY" else SELL,
            )
            signed = self.client.create_order(order_args, options)
            args_list.append(PostOrdersV2Args(order=signed, orderType=OrderType.GTC))
        return self.client.post_orders(args_list)

    def place_market_order(
        self,
        token_id: str,
        side: str,
        size: float,
    ) -> Optional[Dict[Any, Any]]:
        """
        Place a market order (FOK) on Polymarket CLOB.

        Args:
            token_id: The token ID to trade.
            side: "BUY" or "SELL".
            size: BUY -> $$$ amount; SELL -> shares.

        Returns:
            Order response dictionary or None if failed.
        """
        if not self.client:
            print("Error: CLOB client not initialized.")
            return None

        if not CLOB_AVAILABLE or MarketOrderArgs is None or OrderType is None:
            print("Error: py-clob-client-v2 not available.")
            return None

        if side.upper() not in ["BUY", "SELL"]:
            print(f"Error: Invalid side '{side}'. Must be 'BUY' or 'SELL'")
            return None

        max_retries = 3
        delay_sec = 1.5
        for attempt in range(max_retries):
            try:
                order = MarketOrderArgs(
                    token_id=token_id,
                    amount=float(size),
                    side=BUY if side.upper() == "BUY" else SELL,
                    order_type=OrderType.FOK,
                )
                signed = self.client.create_market_order(order)
                resp = self.client.post_order(signed, OrderType.FOK)
                return resp
            except Exception as e:
                self._log_order_error(e, "Error placing market order")
                if attempt < max_retries - 1:
                    print(f"  Retry {attempt + 1}/{max_retries} in {delay_sec}s...")
                    time.sleep(delay_sec)
                else:
                    return None
        return None

    def cancel_all_orders(self) -> Optional[Dict[Any, Any]]:
        """Cancel all open orders for this API key."""
        if not self.client:
            print("Error: CLOB client not initialized.")
            return None

        if not CLOB_AVAILABLE:
            print("Error: py-clob-client-v2 not available.")
            return None

        try:
            resp = self.client.cancel_all()
            return resp
        except Exception as e:
            print(f"Error canceling all orders: {e}")
            return None

    def cancel_order(
        self,
        order_id: str,
        order_type: Optional[str] = None,
    ) -> Optional[Dict[Any, Any]]:
        """
        Cancel a single order.

        v2 expects an `OrderPayload` dataclass instead of a raw order_id string,
        but we keep the wrapper input as a string so call sites don't change.
        """
        if not self.client:
            print("Error: CLOB client not initialized.")
            return None

        if not CLOB_AVAILABLE or OrderPayload is None:
            print("Error: py-clob-client-v2 not available.")
            return None

        try:
            payload = OrderPayload(orderID=order_id)
            return self.client.cancel_order(payload)
        except Exception as e:
            print(f"Error canceling order: {e}")
            return None

    def get_orders(self) -> Optional[List[Dict[Any, Any]]]:
        """
        Get open orders for this API key.

        v2 renamed `get_orders` -> `get_open_orders`; we keep this method name
        for backwards compatibility with the rest of the codebase.
        """
        if not self.client:
            print("Error: CLOB client not initialized.")
            return None
        if not CLOB_AVAILABLE or OpenOrderParams is None:
            return None
        try:
            params = OpenOrderParams()
            return self.client.get_open_orders(params)
        except Exception as e:
            print(f"Error getting orders: {e}")
            return None
