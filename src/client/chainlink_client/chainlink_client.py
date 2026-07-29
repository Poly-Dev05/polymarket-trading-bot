#!/usr/bin/env python3
"""Stream realtime BTC price from Chainlink Data Streams using py_chainlink_streams."""
import asyncio
import logging
import os
import statistics
import sys
import time
from collections import deque
from pathlib import Path
import threading
from typing import Callable, Optional, List, Tuple

# Ensure project root is on path so src.config can be found (whether run from root or src/)
_root = Path(__file__).resolve().parent.parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
try:
    from dotenv import load_dotenv  # pyright: ignore[reportMissingImports]
    load_dotenv(_root / ".env")
except ImportError:
    pass

import config.config as config

try:
    from py_chainlink_streams import ChainlinkClient as ChainlinkStreamsClient, ChainlinkConfig, ReportResponse  # pyright: ignore[reportMissingImports]
    CHAINLINK_STREAMS_AVAILABLE = True
except ImportError:
    ChainlinkStreamsClient = None  # type: ignore[assignment]
    ChainlinkConfig = None  # type: ignore[assignment]
    ReportResponse = None  # type: ignore[assignment]
    CHAINLINK_STREAMS_AVAILABLE = False

logger = logging.getLogger(__name__)

# Delay between full stream restarts after library exhausts its reconnects (seconds)
STREAM_RESTART_DELAY = 5


class ChainlinkClient:
    def __init__(self, feed_id: str, start_stream_thread: bool = True):
        self.streams_config = None
        self.client = None
        self.feed_id = feed_id
        self.feed_ids = [feed_id] if feed_id else []
        self._price_history: deque = deque(maxlen=3000)
        self._last_price: Optional[float] = None
        self._last_update_time: Optional[int] = None
        self.running = True

        api_key = (os.getenv("CHAINLINK_STREAMS_API_KEY") or "").strip()
        api_secret = (os.getenv("CHAINLINK_STREAMS_API_SECRET") or "").strip()
        has_creds = bool(api_key and api_secret)

        if CHAINLINK_STREAMS_AVAILABLE and ChainlinkConfig is not None and ChainlinkStreamsClient is not None and has_creds:
            self.streams_config = ChainlinkConfig(
                api_key=api_key,
                api_secret=api_secret,
                ws_max_reconnect=999999,  # effectively infinite; we still restart in _stream loop if needed
            )
            self.client = ChainlinkStreamsClient(self.streams_config)
        else:
            if not CHAINLINK_STREAMS_AVAILABLE:
                logger.warning("py_chainlink_streams is not installed; Chainlink stream features are disabled.")
            elif not has_creds:
                logger.warning("CHAINLINK_STREAMS_API_KEY/SECRET missing; Chainlink stream features are disabled.")
            else:
                logger.warning("Chainlink streams client unavailable; stream features are disabled.")

        if start_stream_thread and self.client is not None:
            self.thread = threading.Thread(target=self._stream, daemon=True)
            self.thread.start()
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

    def get_price_at_timestamp(self, timestamp: int | float | str) -> float:
        """
        Get the Chainlink Data Streams benchmark price for this feed at a specific Unix timestamp (seconds).

        Uses the authenticated Data Streams API to fetch the report at the given time
        and returns the decoded benchmark price.
        """
        if not self.feed_id:
            raise ValueError("feed_id is not set; cannot get report")
        if self.client is None:
            logger.warning("Chainlink client unavailable; returning 0.0 for get_price_at_timestamp.")
            return 0.0
        # Data Streams expects Unix seconds as an integer string/number.
        try:
            ts_int = int(float(timestamp))
        except (TypeError, ValueError):
            logger.warning("Invalid timestamp for Chainlink report: %r", timestamp)
            return 0.0
        report = self.client.get_report(self.feed_id, ts_int)
        prices = report.get_decoded_prices()
        return float(prices.get("benchmarkPrice", 0.0))

    def _stream(self) -> None:
        if self.client is None:
            logger.warning("Chainlink stream unavailable; _stream exiting.")
            return
        while self.running:
            try:
                if not self.feed_ids:
                    logger.warning("No feed_id configured; stream not started.")
                    break
                asyncio.run(
                    self.client.stream_with_status_callback(
                        self.feed_ids,
                        self._process_report,
                        status_callback=self._on_connection_status,
                    )
                )
            except Exception as e:
                logger.exception("Stream error: %s", e)
            if self.running:
                logger.warning("Connection lost. Restarting stream in %ss...", STREAM_RESTART_DELAY)
                time.sleep(STREAM_RESTART_DELAY)

    def _on_connection_status(self, is_connected: bool, host: str, _origin: str) -> None:
        if is_connected:
            logger.info("Chainlink stream connected to %s", host)
        else:
            logger.warning("Chainlink stream disconnected from %s", host)

    async def _process_report(self, report_data: dict) -> None:
        if ReportResponse is None:
            return
        report = ReportResponse.from_dict(report_data)
        prices = report.get_decoded_prices()
        price = float(prices.get("benchmarkPrice", 0.0))
        config.CURRENT_PRICE = price
