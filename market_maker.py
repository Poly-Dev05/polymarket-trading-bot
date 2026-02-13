#!/usr/bin/env python3
"""
Market Maker - Real-time order book monitoring for Polymarket BTC 5-min markets
Uses PolymarketBot to find markets and PolymarketCLOBWebSocket for live bid/ask data
"""

import os
import time
from datetime import datetime

# Try to load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from polymarket_bot import PolymarketBot
from websocket_client import PolymarketCLOBWebSocket


def main():
    """Initialize bot, find current market, and stream real-time order book data"""

    # ── 1. Load configuration from environment ──────────────────────────
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        print("ERROR: PRIVATE_KEY not set. Export it or add to .env")
        return

    host = os.getenv("HOST", "https://clob.polymarket.com")
    funder = os.getenv("FUNDER")
    chain_id = os.getenv("CHAIN_ID")
    signature_type = os.getenv("SIGNATURE_TYPE")

    # ── 2. Initialize PolymarketBot ─────────────────────────────────────
    bot = PolymarketBot(
        private_key=private_key,
        host=host,
        funder=funder,
        chain_id=chain_id,
        signature_type=signature_type,
    )

    if not bot.client:
        print("❌ CLOB client failed to initialize. Check credentials.")
        return

    # ── 3. Find the current BTC 5-min up/down market ───────────────────
    print("\n🔍 Searching for active BTC 5-min market...")
    market = bot.find_current_market()

    if not market:
        print("❌ Could not find any active BTC up/down 5-minute market")
        return

    # ── 4. Extract Up / Down token IDs ─────────────────────────────────
    token_ids = bot.get_token_ids(market)
    if not token_ids:
        print("❌ Could not extract token IDs from market data")
        return

    up_token = token_ids["up_token_id"]
    down_token = token_ids["down_token_id"]
    print(f"  UP  token: {up_token}")
    print(f"  DOWN token: {down_token}")

    # ── 5. Set up WebSocket client for real-time order book ─────────────
    ws_client = PolymarketCLOBWebSocket()

    # Real-time data store for both outcomes
    realtime_data = {
        "UP":   {"bid": None, "ask": None, "spread": None, "mid": None, "last_update": None},
        "DOWN": {"bid": None, "ask": None, "spread": None, "mid": None, "last_update": None},
    }

    # ── Callbacks ───────────────────────────────────────────────────────
    def on_price_change(data):
        """Handle price_change events — update realtime_data and display"""
        asset_id = data.get("asset_id")
        best_bid = data.get("best_bid")
        best_ask = data.get("best_ask")
        spread = data.get("spread")

        if not asset_id or best_bid is None or best_ask is None:
            return
        if best_bid > best_ask:
            return

        mid_price = (best_bid + best_ask) / 2

        # Map asset to outcome
        if asset_id == up_token:
            outcome = "UP"
        elif asset_id == down_token:
            outcome = "DOWN"
        else:
            return

        realtime_data[outcome] = {
            "bid": best_bid,
            "ask": best_ask,
            "spread": spread,
            "mid": mid_price,
            "last_update": datetime.now(),
        }

        # Only print when we have both sides and asks sum ≈ 1.0
        up_ask = realtime_data["UP"].get("ask")
        down_ask = realtime_data["DOWN"].get("ask")
        if up_ask is not None and down_ask is not None:
            if abs((up_ask + down_ask) - 1.0) > 0.05:
                return  # data not yet consistent
            display_realtime_data()

    def on_book_update(data):
        """Handle full order book snapshots"""
        asset_id = data.get("asset_id")
        best_bid = data.get("best_bid")
        best_ask = data.get("best_ask")
        spread = data.get("spread")

        if not asset_id or best_bid is None or best_ask is None:
            return

        mid_price = (best_bid + best_ask) / 2

        if asset_id == up_token:
            outcome = "UP"
        elif asset_id == down_token:
            outcome = "DOWN"
        else:
            return

        realtime_data[outcome] = {
            "bid": best_bid,
            "ask": best_ask,
            "spread": spread,
            "mid": mid_price,
            "last_update": datetime.now(),
        }

        up_ask = realtime_data["UP"].get("ask")
        down_ask = realtime_data["DOWN"].get("ask")
        if up_ask is not None and down_ask is not None:
            if abs((up_ask + down_ask) - 1.0) > 0.05:
                return
            display_realtime_data()

    def display_realtime_data():
        """Print one line with current best bids/asks for both tokens"""
        now = datetime.now().strftime("%H:%M:%S")
        up = realtime_data["UP"]
        down = realtime_data["DOWN"]

        up_str = (
            f"Bid={up['bid']:.4f} Ask={up['ask']:.4f} Mid={up['mid']:.4f} Sprd={up['spread']:.4f}"
            if up["bid"] is not None else "Waiting..."
        )
        down_str = (
            f"Bid={down['bid']:.4f} Ask={down['ask']:.4f} Mid={down['mid']:.4f} Sprd={down['spread']:.4f}"
            if down["bid"] is not None else "Waiting..."
        )

        print(f"[{now}]  UP: {up_str}  |  DOWN: {down_str}")

    def on_connect():
        """Subscribe to both UP and DOWN tokens once connected"""
        print("✅ WebSocket connected — subscribing to tokens...")
        time.sleep(1)
        ws_client.subscribe([up_token, down_token])

    def on_disconnect(code, msg):
        print(f"⚠️  WebSocket disconnected (code={code})")

    def on_error(err):
        print(f"❌ WebSocket error: {err}")

    # Register callbacks
    ws_client.on_price_change = on_price_change
    ws_client.on_book_update = on_book_update
    ws_client.on_connect = on_connect
    ws_client.on_disconnect = on_disconnect
    ws_client.on_error = on_error

    # ── 6. Connect and stream ──────────────────────────────────────────
    print("\n📡 Connecting to Polymarket CLOB WebSocket...")
    if ws_client.connect(debug=False):
        print("🔄 Streaming real-time order book — press Ctrl+C to stop\n")
        try:
            while ws_client.running:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping...")
            ws_client.disconnect()
    else:
        print("❌ Failed to connect to WebSocket")


if __name__ == "__main__":
    main()
