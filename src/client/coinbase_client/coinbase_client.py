"""
CoinbaseClient — process-isolated WebSocket and REST client for real-time
and historical BTC price data from Coinbase Exchange.

The market-data WebSocket runs in a dedicated child process (see
:mod:`client.coinbase_client.coinbase_ws_worker`) so that GIL contention
from trader threads in the parent (e.g. the busy ``while True`` loops in
``trade()`` in the ``arb_bot*`` scripts) cannot starve the socket reader.
Before this change, a price tick from Coinbase could sit in the kernel
receive buffer for several seconds while the in-process WS thread waited
for the GIL — making ``COIN_BASE_CURRENT_PRICE`` look frozen even though
real Coinbase trades were happening.

Architecture mirrors :mod:`service.ws_worker` / :class:`PolymarketBot`:

* Child process owns ``websocket.WebSocketApp`` and forwards every
  ``match`` frame as a small dict over an ``mp.Queue``.
* Parent runs a single dispatcher thread that drains the queue and
  writes the latest price into :mod:`config` (the only state the rest
  of the bot reads).
* Inactivity watchdog inside the child force-reconnects when no
  ``match`` arrives for 30s while the socket is nominally connected —
  Coinbase's documented silent-freeze recovery.

Public surface (unchanged from the old in-process version):
``start()``, ``stop()``, ``last_price``, ``last_update_time``,
``get_price_at_timestamp()``.
"""
import multiprocessing as mp
import os
import queue as _queue
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional

# Allow imports from project root (src) when running from any entrypoint
_src = Path(__file__).resolve().parent.parent.parent
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

import config.config as config

try:
    import requests
except ImportError:
    requests = None  # type: ignore

from client.coinbase_client.coinbase_ws_worker import coinbase_ws_worker_main

# Use "spawn" so the child starts with a clean Python interpreter and does
# not fork the parent's already-loaded sockets, threads, and CLOB client
# state. Idempotent and harmless if already set elsewhere.
try:
    mp.set_start_method("spawn", force=True)
except RuntimeError:
    pass

# Coinbase Exchange REST endpoint (unchanged; only used by
# ``get_price_at_timestamp`` which is a sync HTTP call, not a WS read).
COINBASE_REST_URL = "https://api.exchange.coinbase.com"


class CoinbaseClient:
    """
    Process-isolated WebSocket client for real-time price data from Coinbase
    Exchange.

    Subscribes to the ``matches`` (trades) channel for the configured
    product (``${ASSET}-USD``, default ``BTC-USD``) and updates
    :mod:`config` with the latest trade price and the wall-clock timestamp
    of that update so callers can detect staleness.
    """

    def __init__(self, debug: bool = False) -> None:
        """
        Initialize CoinbaseClient.

        Args:
            debug: If True, log status/error events received from the
                child process to stdout. Off by default to keep the
                trading logs uncluttered.
        """
        asset = (os.getenv("ASSET") or "BTC").strip().upper() or "BTC"
        self.symbol = f"{asset}-USD"

        self._debug = debug

        # Child-process plumbing — created lazily in start().
        self._ws_proc: Optional[mp.Process] = None
        self._event_q: Optional[Any] = None  # mp.Queue
        self._dispatch_thread: Optional[threading.Thread] = None
        self._dispatch_stop: Optional[threading.Event] = None
        self._running = False

        # Cached locally so callers asking for ``last_price`` /
        # ``last_update_time`` don't need to read the (volatile) ``config``
        # globals. Updated by the dispatcher thread.
        self._last_price: Optional[float] = None
        self._last_update_time: Optional[int] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the child process and dispatcher thread.

        Idempotent: a second call while already running is a no-op.
        """
        if self._running:
            return
        self._running = True

        # Generously sized queue. Coinbase BTC-USD typically trades 5–50
        # times per second; 10k entries gives the parent dispatcher
        # plenty of headroom even under sustained bursts.
        self._event_q = mp.Queue(maxsize=10_000)
        self._dispatch_stop = threading.Event()

        self._ws_proc = mp.Process(
            target=coinbase_ws_worker_main,
            args=(self.symbol, self._event_q),
            name="coinbase-ws-worker",
            daemon=True,
        )
        self._ws_proc.start()

        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop,
            name="coinbase-ws-dispatch",
            daemon=True,
        )
        self._dispatch_thread.start()

    def stop(self) -> None:
        """Stop the child process and dispatcher thread.

        Safe to call multiple times.
        """
        self._running = False

        if self._dispatch_stop is not None:
            self._dispatch_stop.set()
        if self._dispatch_thread is not None:
            try:
                self._dispatch_thread.join(timeout=2.0)
            except Exception:
                pass
            self._dispatch_thread = None

        if self._ws_proc is not None:
            # The worker has no graceful "shutdown" command (none was
            # needed: we just terminate it). Try a clean join first in
            # case it's already exiting on its own, then escalate.
            try:
                self._ws_proc.join(timeout=1.0)
            except Exception:
                pass
            if self._ws_proc.is_alive():
                try:
                    self._ws_proc.terminate()
                    self._ws_proc.join(timeout=2.0)
                except Exception:
                    pass
            self._ws_proc = None

        self._event_q = None
        self._dispatch_stop = None

    def __enter__(self) -> "CoinbaseClient":
        self.start()
        return self

    def __exit__(self, *args: object) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Read-side accessors (kept for API compatibility)
    # ------------------------------------------------------------------

    @property
    def last_price(self) -> Optional[float]:
        """Last received trade price, or None if no update yet."""
        return self._last_price

    @property
    def last_update_time(self) -> Optional[int]:
        """Wall-clock ms timestamp of last price update, or None."""
        return self._last_update_time

    # ------------------------------------------------------------------
    # REST helpers (unchanged behaviour)
    # ------------------------------------------------------------------

    def get_price_at_timestamp(self, market_start_timestamp: int) -> Optional[float]:
        """
        Get BTC price at a given Unix timestamp via Coinbase REST candles.

        Uses the 1-minute candle that starts at that time; returns the open price.

        Args:
            market_start_timestamp: Unix timestamp in seconds.

        Returns:
            Price as float, or None if request fails or no data.
        """
        if not requests:
            return None
        url = f"{COINBASE_REST_URL}/products/{self.symbol}/candles"
        from datetime import datetime, timezone
        start_dt = datetime.fromtimestamp(market_start_timestamp, tz=timezone.utc).isoformat()
        end_dt = datetime.fromtimestamp(market_start_timestamp, tz=timezone.utc).isoformat()
        params = {
            "granularity": 60,
            "start": start_dt,
            "end": end_dt,
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            if not data or not isinstance(data[0], (list, tuple)):
                return None
            # Candle: [ time, low, high, open, close, volume ]
            open_price = float(data[0][3])
            return open_price
        except (requests.RequestException, IndexError, TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Dispatcher (parent side)
    # ------------------------------------------------------------------

    def _dispatch_loop(self) -> None:
        """Drain ``_event_q`` and update :mod:`config` accordingly.

        Runs on a single daemon thread so writes to
        ``config.COIN_BASE_CURRENT_PRICE`` / ``COIN_BASE_LAST_UPDATE_MS``
        are serialized (no torn updates between price and timestamp).

        The whole dispatcher does almost nothing per iteration — just a
        ``Queue.get`` and two attribute assignments — so it can keep up
        with thousands of matches per second even under heavy parent-side
        load.
        """
        stop = self._dispatch_stop
        event_q = self._event_q
        if stop is None or event_q is None:
            return

        while not stop.is_set():
            try:
                msg = event_q.get(timeout=0.5)
            except _queue.Empty:
                continue
            except (EOFError, OSError):
                # Queue closed underneath us (e.g. worker crashed).
                break
            except Exception as e:
                if self._debug:
                    print(f"Coinbase dispatcher error reading event_q: {e}")
                continue

            if not isinstance(msg, dict):
                continue

            etype = msg.get("event_type")

            if etype == "match":
                price = msg.get("price")
                ts_ms = msg.get("ts_ms")
                if not isinstance(price, (int, float)):
                    continue
                price_f = float(price)
                side = msg.get("side")
                # Order matters: write the timestamp last so a reader
                # that observes a fresh COIN_BASE_LAST_UPDATE_MS is
                # guaranteed to also observe the matching price.
                config.COIN_BASE_CURRENT_PRICE = price_f
                config.COIN_BASE_CURRENT_SIDE = side
                if isinstance(ts_ms, (int, float)):
                    config.COIN_BASE_LAST_UPDATE_MS = float(ts_ms)
                else:
                    config.COIN_BASE_LAST_UPDATE_MS = time.time() * 1000.0
                self._last_price = price_f
                self._last_update_time = (
                    int(ts_ms) if isinstance(ts_ms, (int, float)) else int(time.time() * 1000)
                )
                continue

            if etype == "_status":
                if self._debug:
                    state = "connected" if msg.get("connected") else "disconnected"
                    print(f"Coinbase WS {state}")
                continue

            if etype == "_error":
                if self._debug:
                    print(f"Coinbase WS error: {msg.get('error')}")
                continue
