"""
Main strategy / trading parameters.

Tune these defaults (or override via env where noted). Runtime state lives in
``config.config``; scripts should import from there for shared values, and from
here only when they need the static parameter set.
"""
from __future__ import annotations

import os


def _env_float(key: str, default: float | None = None) -> float | None:
    raw = os.getenv(key)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _env_int(key: str, default: int | None = None) -> int | None:
    raw = os.getenv(key)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(float(raw))
    except ValueError:
        return default


def _env_bool(key: str, default: bool = False) -> bool:
    raw = os.getenv(key)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


# ---------------------------------------------------------------------------
# Market / asset
# ---------------------------------------------------------------------------
ASSET: str = (os.getenv("ASSET") or "btc").strip().lower() or "btc"
MARKET_INTERVAL_SECONDS: int = _env_int("MARKET_INTERVAL_SECONDS", 300) or 300
MARKET_SLUG_PREFIX: str = (
    os.getenv("MARKET_SLUG_PREFIX") or f"{ASSET}-updown-5m"
).strip()
PAPER_TRADING: bool = _env_bool("PAPER_TRADING", True)

# ---------------------------------------------------------------------------
# Order sizing
# ---------------------------------------------------------------------------
ORDER_SIZE: float = _env_float("ORDER_SIZE", 30.0) or 30.0
# Aggressive buy limit used by live arb when crossing the book
BUY_LIMIT_PRICE: float = _env_float("BUY_LIMIT_PRICE", 0.99) or 0.99
# Dump / force-sell limit
SELL_LIMIT_PRICE: float = _env_float("SELL_LIMIT_PRICE", 0.01) or 0.01

# ---------------------------------------------------------------------------
# Fees & paper ledger
# ---------------------------------------------------------------------------
FEE_RATE: float = _env_float("FEE_RATE", 0.072) or 0.072
INITIAL_USDC: float = _env_float("INITIAL_USDC", 1000.0) or 1000.0

# ---------------------------------------------------------------------------
# Main strategy parameters — leave empty; set here or via .env before running
# ---------------------------------------------------------------------------
# ROI take-profit
ROI_THRESHOLD_LOW: float | None = _env_float("ROI_THRESHOLD_LOW")
ROI_THRESHOLD_MEDIUM: float | None = _env_float("ROI_THRESHOLD_MEDIUM")
ROI_THRESHOLD_HIGH: float | None = _env_float("ROI_THRESHOLD_HIGH")

# Momentum / signal (Coinbase price deltas, USD)
MOMENTUM_TICK_USD: float | None = _env_float("MOMENTUM_TICK_USD")
MOMENTUM_1S_USD: float | None = _env_float("MOMENTUM_1S_USD")
# Leg-2 hedge: max(abs(price - beat) * factor, floor)
LEG2_DIFF_FACTOR: float | None = _env_float("LEG2_DIFF_FACTOR")
LEG2_DIFF_FLOOR: float | None = _env_float("LEG2_DIFF_FLOOR")
LEG2_DIFF_FLOOR_PAPER: float | None = _env_float("LEG2_DIFF_FLOOR_PAPER")

# Risk / timing
RISK_STOP_TIME_SEC: int | None = _env_int("RISK_STOP_TIME")
MIN_PLACE_INTERVAL_SEC: float = _env_float("MIN_PLACE_INTERVAL_SEC", 0.0) or 0.0
SPLIT_AMOUNT_USDC: float = _env_float("SPLIT_AMOUNT_USDC", 100.0) or 100.0

# ---------------------------------------------------------------------------
# CLOB / chain defaults (non-secret)
# ---------------------------------------------------------------------------
CLOB_API_HOST: str = (
    os.getenv("CLOB_API_HOST") or os.getenv("HOST") or "https://clob.polymarket.com"
).strip()
GAMMA_API_BASE_URL: str = (
    os.getenv("GAMMA_API_BASE_URL") or "https://gamma-api.polymarket.com"
).strip()
CLOB_WS_URL: str = (
    os.getenv("CLOB_WS_URL")
    or "wss://ws-subscriptions-clob.polymarket.com/ws/market"
).strip()
CLOB_WS_USER_URL: str = (
    os.getenv("CLOB_WS_USER_URL")
    or "wss://ws-subscriptions-clob.polymarket.com/ws/user"
).strip()
CHAIN_ID: int = _env_int("CHAIN_ID", 137) or 137
SIGNATURE_TYPE: int = _env_int("SIGNATURE_TYPE", 2) or 2
