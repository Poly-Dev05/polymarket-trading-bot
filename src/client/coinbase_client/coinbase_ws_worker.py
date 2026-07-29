"""WebSocket worker that runs Coinbase Exchange's market-data feed in a
dedicated child process.

This mirrors :mod:`service.ws_worker` (the Polymarket book worker): the only
work this child does is read frames off the socket, JSON-decode them, and
push them onto an ``mp.Queue`` for the parent. Keeping the read loop in its
own process makes it immune to GIL contention from trader threads in the
parent (each spinning ``while True`` in ``trade()`` would otherwise starve
the in-process WS reader and make ``COIN_BASE_CURRENT_PRICE`` look stuck).

This module must remain import-clean (no side effects at import time) so a
freshly spawned child interpreter can load it quickly and deterministically.

Public entry point: :func:`coinbase_ws_worker_main`.

Wire protocol on ``event_q`` (child -> parent)
----------------------------------------------
- ``{"event_type": "match",   "price": float, "ts_ms": int}`` per trade.
- ``{"event_type": "_status", "connected": bool}`` on (dis)connect.
- ``{"event_type": "_error",  "error": str}`` on protocol/library errors.
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any


# Coinbase Exchange market-data WebSocket.
COINBASE_WS_URL = "wss://ws-feed.exchange.coinbase.com"

# Bounds for the auto-reconnect backoff inside the child. Mirrors the
# Polymarket worker so behaviour feels familiar.
_RECONNECT_INITIAL_DELAY_SEC = 1.0
_RECONNECT_MAX_DELAY_SEC = 10.0
_RECONNECT_BACKOFF_FACTOR = 1.5

# Inactivity watchdog: if we've gone this long without a `match` while the
# socket reports connected, force-reconnect. Coinbase's BTC-USD usually
# trades many times per second; 30s of silence means the feed is wedged
# (or we've been throttled) and a fresh TCP connection is the safest
# recovery. The threshold is well above the protocol ping interval so a
# healthy idle socket is never killed.
_INACTIVITY_TIMEOUT_SEC = 30.0
_WATCHDOG_POLL_SEC = 5.0


def _safe_put(queue: Any, msg: dict) -> None:
    """Best-effort put_nowait that swallows full-queue errors.

    Dropping a single price tick is preferable to blocking the socket
    reader. The parent dispatcher should size ``event_q`` generously
    (>= 10k) so this drop path is essentially never reached.
    """
    try:
        queue.put_nowait(msg)
    except Exception:
        pass


def coinbase_ws_worker_main(symbol: str, event_q: Any) -> None:
    """Child-process entry point.

    Args:
        symbol:  Coinbase product id (e.g. ``"BTC-USD"``).
        event_q: ``multiprocessing.Queue`` for child -> parent traffic.
    """
    # Local import keeps this module import-clean (no top-level
    # ``websocket`` import means a parent that never spawns the worker
    # doesn't pay the import cost).
    import websocket

    state: dict = {
        "ws": None,                  # active websocket.WebSocketApp, or None
        "connected": False,
        "stop": False,
        "last_match_monotonic": 0.0,  # time.monotonic() of most recent match
    }

    def emit_status(connected: bool) -> None:
        _safe_put(event_q, {"event_type": "_status", "connected": connected})

    def on_open(ws):  # noqa: ARG001 — websocket-client passes the app
        state["connected"] = True
        # Reset the watchdog clock on every (re)connect so the very first
        # window is the full _INACTIVITY_TIMEOUT_SEC, not some leftover.
        state["last_match_monotonic"] = time.monotonic()
        emit_status(True)
        try:
            ws.send(json.dumps({
                "type": "subscribe",
                "product_ids": [symbol],
                "channels": ["ticker"],
            }))
        except Exception as e:
            _safe_put(event_q, {
                "event_type": "_error",
                "error": f"subscribe failed: {e}",
            })

    def on_close(ws, status_code, reason):  # noqa: ARG001
        state["connected"] = False
        emit_status(False)

    def on_error(ws, error):  # noqa: ARG001
        _safe_put(event_q, {"event_type": "_error", "error": str(error)})

    def on_message(ws, message):  # noqa: ARG001
        # ``websocket-client`` may deliver text frames as bytes when
        # ``skip_utf8_validation=True``; handle both forms.
        if not message:
            return
        if isinstance(message, bytes):
            try:
                message = message.decode("utf-8")
            except UnicodeDecodeError:
                return
        try:
            
            data = json.loads(message)
            # print("data", data)
        except json.JSONDecodeError:
            return
        if not isinstance(data, dict):
            return
        # ``matches`` channel publishes a single trade per frame; ignore
        # everything else (subscriptions ack, heartbeats we didn't ask for,
        # last_match snapshot frame, etc.).
        if data.get("type") not in ["ticker"]:
            return
        if data.get("product_id") != symbol:
            return
        try:
            # print("data", data)
            # size = float(data["last_size"])
            side = data["side"]
            price = float(data["price"])
            # best_bid = float(data["best_bid"])
            # best_ask = float(data["best_ask"])
            # best_bid_size = float(data["best_bid_size"])
            # best_ask_size = float(data["best_ask_size"])
            # print(f"size: {size}, side: {side}, price: {price}, best_bid: {best_bid}, best_ask: {best_ask}, best_bid_size: {best_bid_size}, best_ask_size: {best_ask_size}")

        except (KeyError, TypeError, ValueError):
            return
        state["last_match_monotonic"] = time.monotonic()
        _safe_put(event_q, {
            "event_type": "match",
            "price": price,
            "side": side,
            "ts_ms": int(time.time() * 1000),
        })

    def inactivity_watchdog() -> None:
        """Force-reconnect when no ``match`` arrives for too long.

        Coinbase occasionally accepts the subscribe but stops pushing
        trades while the TCP connection (and ping/pong) stays healthy.
        The symptom in the bot is a frozen ``COIN_BASE_CURRENT_PRICE``
        even though real Coinbase trades are happening.

        We only act when we're nominally connected; resetting the
        timestamp after a trigger prevents a re-trip on the same socket
        while the close+reconnect cycle is in flight.
        """
        while not state["stop"]:
            time.sleep(_WATCHDOG_POLL_SEC)
            if not state["connected"]:
                continue
            last = state.get("last_match_monotonic") or 0.0
            if last <= 0.0:
                continue
            if time.monotonic() - last < _INACTIVITY_TIMEOUT_SEC:
                continue
            ws = state["ws"]
            if ws is None:
                continue
            _safe_put(event_q, {
                "event_type": "_error",
                "error": (
                    f"inactivity watchdog: no Coinbase match for "
                    f"{_INACTIVITY_TIMEOUT_SEC:.0f}s — forcing reconnect"
                ),
            })
            try:
                ws.close()
            except Exception:
                pass
            # Avoid immediately re-tripping on the new socket before its
            # first frame lands.
            state["last_match_monotonic"] = time.monotonic()

    threading.Thread(
        target=inactivity_watchdog,
        daemon=True,
        name="coinbase-ws-watchdog",
    ).start()

    # Auto-reconnect supervision loop. ``run_forever`` returns whenever the
    # socket closes (cleanly or otherwise); we then back off and retry
    # until ``stop`` is set. There is no parent-side "shutdown" command on
    # purpose: the parent simply terminates the process via ``Process.terminate()``.
    delay = _RECONNECT_INITIAL_DELAY_SEC
    while not state["stop"]:
        ws_app = websocket.WebSocketApp(
            COINBASE_WS_URL,
            on_open=on_open,
            on_close=on_close,
            on_error=on_error,
            on_message=on_message,
        )
        state["ws"] = ws_app
        try:
            # Coinbase honours the WS protocol-level ping/pong, so we can
            # rely on it for dead-TCP detection. ping_interval > ping_timeout
            # is a websocket-client requirement.
            ws_app.run_forever(
                ping_interval=20,
                ping_timeout=10,
                skip_utf8_validation=True,
            )
        except Exception as e:
            _safe_put(event_q, {"event_type": "_error", "error": str(e)})
        finally:
            state["ws"] = None
            state["connected"] = False

        if state["stop"]:
            break

        time.sleep(delay)
        delay = min(delay * _RECONNECT_BACKOFF_FACTOR, _RECONNECT_MAX_DELAY_SEC)
