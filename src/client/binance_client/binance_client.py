"""
BinanceClient - WebSocket and REST client for real-time and historical BTC price data from Binance.
"""
from datetime import datetime
import json
import os
import statistics
import threading
import time
from collections import deque
from typing import Callable, Optional, List, Tuple

import sys
from pathlib import Path

# Allow imports from project root (src) when running from any entrypoint
_src = Path(__file__).resolve().parent.parent.parent
if _src not in sys.path:
    sys.path.insert(0, str(_src))

import config.config as config
import websocket  # pyright: ignore[reportMissingImports]

try:
    import requests
except ImportError:
    requests = None  # type: ignore

# Binance Spot WebSocket and REST base URLs
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws"
BINANCE_REST_URL = "https://api.binance.com"


class BinanceClient:
    """
    WebSocket client for real-time price data from Binance.

    Subscribes to the trade stream for the given symbol (default: btcusdt)
    and invokes a callback on each price update.
    """

    def __init__(
        self,
        symbol: str = "btcusdt",
        on_price: Optional[Callable[[float, float, int], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        """
        Initialize BinanceClient.

        Args:
            symbol: Trading pair in lowercase (e.g. "btcusdt").
            on_price: Callback(current_price, quantity, timestamp_ms) on each trade.
            on_error: Optional callback for connection/parse errors.
        """
        self.symbol = (os.getenv("ASSET") or "btc").strip().lower() + "usdt"
        self.on_price = on_price
        self.on_error = on_error
        self._ws: Optional[websocket.WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._last_price: Optional[float] = None
        self._last_update_time: Optional[int] = None
        # Rolling (timestamp_ms, price) for 6s/8s/10s lookback (keep last 11s)
        self._price_history: deque = deque(maxlen=3000)

    def _price_at_ago_ms(self, history: List[Tuple[int, float]], now_ms: int, ago_ms: int) -> Optional[float]:
        """Return price from history closest to (now_ms - ago_ms)."""
        target = now_ms - ago_ms
        if not history:
            return None
        best_price: Optional[float] = None
        best_diff = float("inf")
        for ts, price in history:
            diff = abs(ts - target)
            if diff < best_diff:
                best_diff = diff
                best_price = price
        return best_price

    @property
    def last_price(self) -> Optional[float]:
        """Last received trade price, or None if no update yet."""
        return self._last_price

    @property
    def last_update_time(self) -> Optional[int]:
        """Timestamp (ms) of last price update, or None."""
        return self._last_update_time

    def get_price_at_timestamp(self, market_start_timestamp: int) -> Optional[float]:
        """
        Get BTC price at a given Unix timestamp (e.g. market start) via Binance REST klines.

        Uses the 1-minute candle that starts at that time; returns the open price.

        Args:
            market_start_timestamp: Unix timestamp in seconds (e.g. from slug btc-updown-5m-{ts}).

        Returns:
            Price as float, or None if request fails or no data.
        """
        if not requests:
            return None
        url = f"{BINANCE_REST_URL}/api/v3/klines"
        # Binance expects milliseconds
        start_ms = int(market_start_timestamp) * 1000
        params = {
            "symbol": self.symbol.upper(),
            "interval": "1m",
            "startTime": start_ms,
            "limit": 1,
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            if not data or not isinstance(data[0], (list, tuple)):
                return None
            # Kline: [open_time, open, high, low, close, volume, ...]
            open_price = float(data[0][1])
            return open_price
        except (requests.RequestException, IndexError, TypeError, ValueError):
            return None

    def _ws_url(self) -> str:
        """Stream URL for this symbol's trades."""
        return f"{BINANCE_WS_URL}/{self.symbol}@trade"

    def _on_message(self, _ws: websocket.WebSocketApp, message: str) -> None:
        try:
            data = json.loads(message)
            if data.get("e") != "trade":
                return
            price = float(data["p"])
            config.BINANCE_CURRENT_PRICE = price


           
        except (KeyError, TypeError, ValueError) as e:
            if self.on_error:
                self.on_error(e)

    def _on_error(self, _ws: websocket.WebSocketApp, error: Exception) -> None:
        if self.on_error:
            self.on_error(error)

    def _run_ws(self) -> None:
        self._ws = websocket.WebSocketApp(
            self._ws_url(),
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=lambda *_: None,
        )
        while self._running and self._ws:
            self._ws.run_forever(ping_interval=20, ping_timeout=10)
            # if self._running:
            #     time.sleep(1)

    def start(self) -> None:
        """Start the WebSocket connection in a background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_ws, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the WebSocket connection."""
        self._running = False
        if self._ws:
            self._ws.close()
            self._ws = None
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def __enter__(self) -> "BinanceClient":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()
