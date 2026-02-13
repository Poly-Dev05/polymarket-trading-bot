#!/usr/bin/env python3
"""
Polymarket CLOB WebSocket Client
Connects to Polymarket CLOB WebSocket for real-time order book data
"""

import json
import time
import threading
import websocket
import requests
from datetime import datetime
from typing import Optional, Dict, List, Callable
from dotenv import load_dotenv
import os

load_dotenv()

class PolymarketCLOBWebSocket:
    def __init__(self):
        """Initialize Polymarket CLOB WebSocket connection"""
        # Use /ws/market channel for market data
        self.WS_URL = os.getenv("CLOB_WS_URL")
        self.CLOB_API_BASE = os.getenv("CLOB_API_BASE")
        
        # WebSocket connection
        self.ws = None
        self.ws_thread = None
        self.connected = False
        self.running = False
        
        # Subscriptions
        self.subscribed_assets: List[str] = []
        self.subscribed_markets: List[str] = []
        
        # Order book data storage
        self.order_books: Dict[str, Dict] = {}  # asset_id -> {bids: [], asks: [], timestamp}
        
        # Callbacks
        self.on_book_update: Optional[Callable] = None
        self.on_price_change: Optional[Callable] = None
        self.on_trade: Optional[Callable] = None
        self.on_connect: Optional[Callable] = None
        self.on_disconnect: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        # Handle empty or binary messages (ping/pong)
        if not message or len(message) == 0:
            return
        
        # Skip binary ping/pong frames
        if isinstance(message, bytes):
            return
        
        try:
            data = json.loads(message)
            # print(f"Received message: {data}")
            # Handle if data is a list (array of events)
            if isinstance(data, list):
                for item in data:
                    self._process_single_message(item)
            else:
                self._process_single_message(data)
                
        except json.JSONDecodeError:
            # Skip non-JSON messages (like ping/pong)
            pass
        except Exception as e:
            if hasattr(self, '_debug') and self._debug:
                print(f"Error processing message: {e}")
            if self.on_error:
                self.on_error(e)
    
    def _process_single_message(self, data):
        """Process a single message object"""
        if not isinstance(data, dict):
            return
        
        event_type = data.get("event_type") or data.get("type") or data.get("event")
        
        # Check for price_changes array (main format)
        if "price_changes" in data or (isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "asset_id" in data[0] and "side" in data[0]):
            self._handle_price_change(data)
        elif event_type == "book":
            self._handle_book_update(data)
        elif event_type == "price_change":
            self._handle_price_change(data)
        elif event_type == "last_trade_price":
            self._handle_trade(data)
        elif event_type == "subscribed" or data.get("subscribed"):
            pass  # Subscription confirmed silently
        elif event_type == "error" or data.get("error"):
            pass  # Errors handled elsewhere
        elif event_type == "ping":
            # Respond to ping
            pong_msg = {"type": "pong"}
            self.ws.send(json.dumps(pong_msg))
        elif event_type == "pong":
            pass
    
    def _handle_book_update(self, data: Dict):
        """Handle order book update"""
        # Handle different possible field names
        asset_id = data.get("asset_id") or data.get("assetId") or data.get("token_id")
        market_id = data.get("market") or data.get("market_id")
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        timestamp = data.get("timestamp")
        
        # Debug logging removed - logs now accumulate instead of overwriting
        
        if not asset_id:
            return
        
        # Store order book data
        self.order_books[asset_id] = {
            "bids": bids,
            "asks": asks,
            "market_id": market_id,
            "timestamp": timestamp,
            "last_update": datetime.now()
        }
        
        # Extract best bid and ask - handle different formats
        best_bid = None
        best_ask = None
        
        # Bids are sorted descending (highest first)
        if bids and len(bids) > 0:
            bid = bids[0]
            try:
                if isinstance(bid, dict):
                    # Try multiple possible price field names
                    best_bid = float(
                        bid.get("price") or 
                        bid.get("px") or 
                        bid.get("p") or 
                        bid.get("priceNum") or
                        0
                    )
                elif isinstance(bid, (list, tuple)) and len(bid) >= 1:
                    # Format: [price, size] - price is first element
                    best_bid = float(bid[0])
                elif isinstance(bid, str):
                    best_bid = float(bid)
                else:
                    best_bid = float(bid)
            except (ValueError, TypeError, IndexError):
                best_bid = None
        
        # Asks are sorted ascending (lowest first)
        if asks and len(asks) > 0:
            ask = asks[0]
            try:
                if isinstance(ask, dict):
                    # Try multiple possible price field names
                    best_ask = float(
                        ask.get("price") or 
                        ask.get("px") or 
                        ask.get("p") or 
                        ask.get("priceNum") or
                        0
                    )
                elif isinstance(ask, (list, tuple)) and len(ask) >= 1:
                    # Format: [price, size] - price is first element
                    best_ask = float(ask[0])
                elif isinstance(ask, str):
                    best_ask = float(ask)
                else:
                    best_ask = float(ask)
            except (ValueError, TypeError, IndexError):
                best_ask = None
        
        # Only call callback if we have valid prices
        if best_bid and best_ask and self.on_book_update:
            self.on_book_update({
                "asset_id": asset_id,
                "market_id": market_id,
                "bids": bids,
                "asks": asks,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": best_ask - best_bid,
                "timestamp": timestamp
            })
    
    def _handle_price_change(self, data: Dict):
        """Handle price change event"""
        # Handle price_changes array
        price_changes = data.get("price_changes", [])
        if not price_changes and isinstance(data, list):
            price_changes = data
        
        if price_changes:
            for change in price_changes:
                if isinstance(change, dict):
                    asset_id = change.get("asset_id")
                    side = change.get("side")  # "BUY" or "SELL"
                    price = change.get("price")
                    
                    if asset_id and price:
                        try:
                            price_float = float(price)
                            # Store price by asset_id and side
                            if asset_id not in self.order_books:
                                self.order_books[asset_id] = {}
                            
                            if side == "BUY":
                                # BUY side = best bid
                                self.order_books[asset_id]["best_bid"] = price_float
                            elif side == "SELL":
                                # SELL side = best ask
                                self.order_books[asset_id]["best_ask"] = price_float
                            
                            # Only call callback if we have both bid and ask for this asset
                            if "best_bid" in self.order_books[asset_id] and "best_ask" in self.order_books[asset_id]:
                                bid = self.order_books[asset_id]["best_bid"]
                                ask = self.order_books[asset_id]["best_ask"]
                                
                                # Validate: bid should be <= ask
                                if bid and ask and bid <= ask:
                                    if self.on_price_change:
                                        self.on_price_change({
                                            "asset_id": asset_id,
                                            "best_bid": bid,
                                            "best_ask": ask,
                                            "spread": ask - bid if (bid and ask) else None
                                        })
                        except (ValueError, TypeError):
                            pass
        
        # Also handle single price_change event (backward compatibility)
        elif self.on_price_change:
            self.on_price_change(data)
    
    def _handle_trade(self, data: Dict):
        """Handle last trade price event"""
        if self.on_trade:
            self.on_trade(data)
    
    def on_error_handler(self, ws, error):
        """Handle WebSocket errors"""
        # Only log critical errors
        if self.on_error:
            self.on_error(error)
    
    def on_close_handler(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        self.connected = False
        if self.on_disconnect:
            self.on_disconnect(close_status_code, close_msg)
        
        # Auto-reconnect if still running
        if self.running:
            time.sleep(5)
            if self.running:
                self.connect()
    
    def on_open_handler(self, ws):
        """Handle WebSocket open"""
        self.connected = True
        
        # Start keepalive ping
        self._start_keepalive()
        
        if self.on_connect:
            self.on_connect()
        
        # Resubscribe to previous subscriptions
        if self.subscribed_assets:
            time.sleep(1)
            self._subscribe(self.subscribed_assets, self.subscribed_markets)
    
    def _start_keepalive(self):
        """Start keepalive ping to maintain connection"""
        def keepalive():
            while self.running and self.connected:
                try:
                    time.sleep(25)
                    if self.ws and self.connected:
                        ping_msg = {"type": "ping"}
                        self.ws.send(json.dumps(ping_msg))
                except:
                    self.connected = False
                    break
        
        keepalive_thread = threading.Thread(target=keepalive, daemon=True)
        keepalive_thread.start()
    
    def _subscribe(self, asset_ids: List[str], market_ids: List[str] = None):
        """Send subscription message"""
        if not self.connected or not self.ws:
            return False
        
        subscribe_msg = {
            "type": "market",
            "assets_ids": asset_ids
        }
        
        try:
            msg_str = json.dumps(subscribe_msg)
            self.ws.send(msg_str)
            self.subscribed_assets = asset_ids
            self.subscribed_markets = market_ids or []
            time.sleep(1)
            
            if not self.connected:
                return False
            
            return True
        except Exception as e:
            return False
    
    def subscribe(self, asset_ids: List[str], market_ids: List[str] = None):
        """
        Subscribe to order book updates for specific assets
        
        Args:
            asset_ids: List of token/asset IDs to subscribe to
            market_ids: Optional list of market/condition IDs
        """
        if not isinstance(asset_ids, list):
            asset_ids = [asset_ids]
        
        if market_ids and not isinstance(market_ids, list):
            market_ids = [market_ids]
        
        return self._subscribe(asset_ids, market_ids)
    
    def get_order_book(self, asset_id: str) -> Optional[Dict]:
        """Get current order book for an asset"""
        return self.order_books.get(asset_id)
    
    def get_best_bid_ask(self, asset_id: str) -> Dict:
        """Get best bid and ask prices for an asset"""
        order_book = self.get_order_book(asset_id)
        
        if not order_book:
            return {"best_bid": None, "best_ask": None, "spread": None}
        
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        
        # Handle different bid/ask formats
        best_bid = None
        best_ask = None
        bid_size = None
        ask_size = None
        
        if bids and len(bids) > 0:
            bid = bids[0]
            if isinstance(bid, dict):
                best_bid = float(bid.get("price", 0))
                bid_size = float(bid.get("size", 0))
            elif isinstance(bid, (list, tuple)) and len(bid) >= 2:
                best_bid = float(bid[0])
                bid_size = float(bid[1])
            else:
                best_bid = float(bid)
        
        if asks and len(asks) > 0:
            ask = asks[0]
            if isinstance(ask, dict):
                best_ask = float(ask.get("price", 0))
                ask_size = float(ask.get("size", 0))
            elif isinstance(ask, (list, tuple)) and len(ask) >= 2:
                best_ask = float(ask[0])
                ask_size = float(ask[1])
            else:
                best_ask = float(ask)
        
        spread = best_ask - best_bid if (best_bid and best_ask) else None
        
        return {
            "best_bid": best_bid,
            "best_ask": best_ask,
            "spread": spread,
            "bid_size": bid_size,
            "ask_size": ask_size
        }
    
    def get_order_book_summary(self) -> Dict:
        """Get summary of all order books"""
        summary = {}
        for asset_id, order_book in self.order_books.items():
            best = self.get_best_bid_ask(asset_id)
            summary[asset_id] = {
                "best_bid": best["best_bid"],
                "best_ask": best["best_ask"],
                "spread": best["spread"],
                "bid_size": best["bid_size"],
                "ask_size": best["ask_size"],
                "num_bids": len(order_book.get("bids", [])),
                "num_asks": len(order_book.get("asks", [])),
                "last_update": order_book.get("last_update")
            }
        return summary
    
    def get_order_book_from_rest(self, token_id: str) -> Optional[Dict]:
        """Get order book from CLOB REST API"""
        try:
            url = f"{self.CLOB_API_BASE}/book"
            params = {"token_id": token_id}
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return data
        except Exception as e:
            pass
        return None
    
    def get_price_from_rest(self, token_id: str) -> Optional[Dict]:
        """Get best bid and ask prices from CLOB REST API"""
        book = self.get_order_book_from_rest(token_id)
        if not book:
            return None
        
        try:
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            
            best_bid = None
            best_ask = None
            
            # Bids are sorted descending (highest first)
            if bids and len(bids) > 0:
                bid = bids[0]
                if isinstance(bid, dict):
                    best_bid = float(bid.get("price") or bid.get("px") or bid.get("p") or 0)
                elif isinstance(bid, (list, tuple)) and len(bid) >= 1:
                    best_bid = float(bid[0])
                else:
                    best_bid = float(bid)
            
            # Asks are sorted ascending (lowest first)
            if asks and len(asks) > 0:
                ask = asks[0]
                if isinstance(ask, dict):
                    best_ask = float(ask.get("price") or ask.get("px") or ask.get("p") or 0)
                elif isinstance(ask, (list, tuple)) and len(ask) >= 1:
                    best_ask = float(ask[0])
                else:
                    best_ask = float(ask)
            
            if best_bid and best_ask:
                return {
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "spread": best_ask - best_bid
                }
        except Exception as e:
            pass
        return None
    
    def connect(self, debug: bool = False):
        """Connect to Polymarket CLOB WebSocket"""
        if self.connected:
            return True
        
        self._debug = debug  # Enable debug mode
        
        self.ws = websocket.WebSocketApp(
            self.WS_URL,
            on_message=self.on_message,
            on_error=self.on_error_handler,
            on_close=self.on_close_handler,
            on_open=self.on_open_handler
        )
        
        self.running = True
        
        def run_ws():
            try:
                self.ws.run_forever(
                    ping_interval=20,
                    ping_timeout=10
                )
            except Exception as e:
                self.connected = False
        
        self.ws_thread = threading.Thread(target=run_ws, daemon=True)
        self.ws_thread.start()
        
        # Wait for connection
        timeout = 15
        start_time = time.time()
        while not self.connected and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if not self.connected:
            return False
        
        return True
    
    def disconnect(self):
        """Disconnect from WebSocket"""
        self.running = False
        self.connected = False
        
        if self.ws:
            self.ws.close()
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.connected
