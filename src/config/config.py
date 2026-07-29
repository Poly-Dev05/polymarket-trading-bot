"""
Shared runtime state for arb bots and market-data clients.

Static / tunable defaults live in ``config.params``. This module re-exports
the main ones and holds the mutable book / price / PnL state that clients and
strategy scripts update at runtime.
"""
from __future__ import annotations

import os
import time
from collections import deque

from config.params import (
    ASSET,
    BUY_LIMIT_PRICE,
    CLOB_API_HOST,
    CLOB_WS_URL,
    CLOB_WS_USER_URL,
    CHAIN_ID,
    FEE_RATE,
    GAMMA_API_BASE_URL,
    INITIAL_USDC as _INITIAL_USDC_DEFAULT,
    LEG2_DIFF_FACTOR,
    LEG2_DIFF_FLOOR,
    LEG2_DIFF_FLOOR_PAPER,
    MARKET_INTERVAL_SECONDS,
    MARKET_SLUG_PREFIX,
    MIN_PLACE_INTERVAL_SEC,
    MOMENTUM_1S_USD,
    MOMENTUM_TICK_USD,
    ORDER_SIZE,
    PAPER_TRADING,
    RISK_STOP_TIME_SEC,
    ROI_THRESHOLD_HIGH,
    ROI_THRESHOLD_LOW,
    ROI_THRESHOLD_MEDIUM,
    SELL_LIMIT_PRICE,
    SIGNATURE_TYPE,
    SPLIT_AMOUNT_USDC,
)

# Polygon mainnet — Polymarket Conditional Tokens (ERC1155).
CTF_ADDRESS: str = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"


def fetch_ctf_outcome_balances_shares(
    up_token_id: str,
    down_token_id: str,
):
    """
    On-chain outcome share balances for UP/DOWN CLOB token ids (CTF ERC1155).

    Returns ``(up_shares, down_shares)`` in human units (raw / 1e6), or
    ``(0, 0)`` / ``None`` on error / missing inputs.
    Requires ``POLYGON_RPC`` and ``FUNDER``.
    """
    try:
        from web3 import Web3
    except ImportError:
        return None

    rpc = os.getenv("POLYGON_RPC")
    w = os.getenv("FUNDER")
    u_tid = (up_token_id or "").strip()
    d_tid = (down_token_id or "").strip()
    if not rpc or not w or not u_tid or not d_tid:
        return None
    abi = [
        {
            "inputs": [
                {"name": "account", "type": "address"},
                {"name": "id", "type": "uint256"},
            ],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "stateMutability": "view",
            "type": "function",
        }
    ]
    try:
        w3 = Web3(Web3.HTTPProvider(rpc))
        if not w3.is_connected():
            return 0, 0
        c = w3.eth.contract(address=Web3.to_checksum_address(CTF_ADDRESS), abi=abi)
        owner = Web3.to_checksum_address(w)
        up_shares = int(c.functions.balanceOf(owner, int(u_tid)).call())
        down_shares = int(c.functions.balanceOf(owner, int(d_tid)).call())
        return up_shares / 1_000_000.0, down_shares / 1_000_000.0
    except Exception:
        return 0, 0


def calculate_fee(c: float, fee_rate: float, p: float) -> float:
    """fee = c * fee_rate * p * (1 - p)."""
    return c * fee_rate * p * (1.0 - p)


def round_usdc(value: float) -> float:
    """Round paper USDC ledger amounts to 2 decimals."""
    return round(value, 2)


def leg2_diff(crypto_price: float, beat: float, *, paper: bool | None = None) -> float:
    """Second-leg trigger distance from spot vs interval beat price.

    Requires ``LEG2_DIFF_FACTOR`` and the matching floor to be set in params.
    """
    if LEG2_DIFF_FACTOR is None:
        raise ValueError("Set LEG2_DIFF_FACTOR in config.params (or .env) before trading")
    use_paper = PAPER_TRADING if paper is None else paper
    floor = LEG2_DIFF_FLOOR_PAPER if use_paper else LEG2_DIFF_FLOOR
    if floor is None:
        raise ValueError(
            "Set LEG2_DIFF_FLOOR / LEG2_DIFF_FLOOR_PAPER in config.params (or .env)"
        )
    return max(abs(crypto_price - beat) * LEG2_DIFF_FACTOR, floor)


# ---------------------------------------------------------------------------
# Runtime market / spot state (mutated by clients + strategy loops)
# ---------------------------------------------------------------------------
PRICE_TO_BEAT: float = 0.0
PRICE_TO_BEAT_COINBASE: float = 0.0
COIN_BASE_CURRENT_PRICE: float = 0.0
COIN_BASE_CURRENT_SIDE: str = ""
COIN_BASE_LAST_UPDATE_MS: float = 0.0
PREV_COIN_BASE_CURRENT_PRICE: float = 0.0
PREV_COIN_BASE_PRICE_1S: float = 0.0

COIN_PRICE_HISTORY: deque = deque(maxlen=10)
COIN_PRICE_AVG: float = 0.0

BINANCE_CURRENT_PRICE: float = 0.0
DIFF: float = 0.0
PREV_MOMENTUM_PRICE: float = 0.0
CURRENT_PRICE: float = 0.0

BEST_ASK: float = 0.0
BEST_BID: float = 0.0
PREV_BEST_ASK: float = 0.0
PREV_BEST_BID: float = 0.0
UP_TRADING_ENABLED: bool = True
DOWN_TRADING_ENABLED: bool = True
TRADING_HALTED: bool = False

COST_USDC: float = round_usdc(0.0)
COST_UP_SHARE: float = 0.0
COST_DOWN_SHARE: float = 0.0
INITIAL_USDC: float = round_usdc(_INITIAL_USDC_DEFAULT)

UP_ROI: float = 0.0
DOWN_ROI: float = 0.0
ROI: float = 0.0
WIN_COUNT: int = 0
LOSS_COUNT: int = 0
BIG_WIN_COUNT: int = 0
LAST_PLACE_TS: float = 0.0


def reset_coin_price_history() -> None:
    """Clear rolling history at the start of each market."""
    global COIN_PRICE_AVG
    COIN_PRICE_HISTORY.clear()
    COIN_PRICE_AVG = 0.0


def record_coin_price_sample(price: float) -> float | None:
    """Append one (timestamp, price) sample and return the rolling average."""
    if price <= 0:
        return None
    COIN_PRICE_HISTORY.append((time.time(), price))
    return sum(p for _, p in COIN_PRICE_HISTORY) / len(COIN_PRICE_HISTORY)


def reset_position_state() -> None:
    """Clear per-market position / ROI counters (call on market rollover)."""
    global COST_USDC, COST_UP_SHARE, COST_DOWN_SHARE
    global ROI, UP_ROI, DOWN_ROI
    global TRADING_HALTED, UP_TRADING_ENABLED, DOWN_TRADING_ENABLED
    COST_USDC = round_usdc(0.0)
    COST_UP_SHARE = 0.0
    COST_DOWN_SHARE = 0.0
    ROI = 0.0
    UP_ROI = 0.0
    DOWN_ROI = 0.0
    TRADING_HALTED = False
    UP_TRADING_ENABLED = True
    DOWN_TRADING_ENABLED = True


__all__ = [
    # params re-export
    "ASSET",
    "BUY_LIMIT_PRICE",
    "CLOB_API_HOST",
    "CLOB_WS_URL",
    "CLOB_WS_USER_URL",
    "CHAIN_ID",
    "FEE_RATE",
    "GAMMA_API_BASE_URL",
    "LEG2_DIFF_FACTOR",
    "LEG2_DIFF_FLOOR",
    "LEG2_DIFF_FLOOR_PAPER",
    "MARKET_INTERVAL_SECONDS",
    "MARKET_SLUG_PREFIX",
    "MIN_PLACE_INTERVAL_SEC",
    "MOMENTUM_1S_USD",
    "MOMENTUM_TICK_USD",
    "ORDER_SIZE",
    "PAPER_TRADING",
    "RISK_STOP_TIME_SEC",
    "ROI_THRESHOLD_HIGH",
    "ROI_THRESHOLD_LOW",
    "ROI_THRESHOLD_MEDIUM",
    "SELL_LIMIT_PRICE",
    "SIGNATURE_TYPE",
    "SPLIT_AMOUNT_USDC",
    # helpers
    "CTF_ADDRESS",
    "calculate_fee",
    "fetch_ctf_outcome_balances_shares",
    "leg2_diff",
    "record_coin_price_sample",
    "reset_coin_price_history",
    "reset_position_state",
    "round_usdc",
    # runtime state
    "BEST_ASK",
    "BEST_BID",
    "BIG_WIN_COUNT",
    "BINANCE_CURRENT_PRICE",
    "COIN_BASE_CURRENT_PRICE",
    "COIN_BASE_CURRENT_SIDE",
    "COIN_BASE_LAST_UPDATE_MS",
    "COIN_PRICE_AVG",
    "COIN_PRICE_HISTORY",
    "COST_DOWN_SHARE",
    "COST_UP_SHARE",
    "COST_USDC",
    "CURRENT_PRICE",
    "DIFF",
    "DOWN_ROI",
    "DOWN_TRADING_ENABLED",
    "INITIAL_USDC",
    "LAST_PLACE_TS",
    "LOSS_COUNT",
    "PREV_BEST_ASK",
    "PREV_BEST_BID",
    "PREV_COIN_BASE_CURRENT_PRICE",
    "PREV_COIN_BASE_PRICE_1S",
    "PREV_MOMENTUM_PRICE",
    "PRICE_TO_BEAT",
    "PRICE_TO_BEAT_COINBASE",
    "ROI",
    "TRADING_HALTED",
    "UP_ROI",
    "UP_TRADING_ENABLED",
    "WIN_COUNT",
]
