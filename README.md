# Polymarket HFT MM Bot

**High-frequency market-making bot** for Polymarket crypto **Up/Down** markets. Quotes both sides throughout each interval, captures spread, and rotates inventory — **unaffected by platform updates** (including Polymarket’s TWAP price change).

**🌐 Language:** [English](README.md) | [中文](README.zh-CN.md) | [Français](README.fr.md) | [Español](README.es.md)

---

## Profile

| | |
|--|--|
| **Telegram** | [`@dizzy`](https://t.me/dizzy283) |
| **Polymarket** | [`@flippingsharks`](https://polymarket.com/@flippingsharks) |
| **Wallet** | [`0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4`](https://polymarket.com/profile/0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4) |

---

## Demo video

📹 **HFT MM bot — live demo**

Preview plays automatically below. **Click the preview to open the full video**.

[![HFT MM bot — live demo](assets/demo-preview.gif)](https://github.com/Poly-Dev05/polymarket-trading-bot/blob/main/assets/demo-video.mp4)

What the recording shows:

1. Bot connected to Polymarket as **`@flippingsharks`**
2. Live crypto **Up/Down** markets (BTC and other assets)
3. Continuous **two-sided quoting** — bids and asks updating in real time
4. Order flow, fills, and inventory rotation across the interval
5. Portfolio, P/L, and trade history on the Polymarket profile

---

## Strategy

| | |
|--|--|
| **Previous strategy** | **Endcycle Sniper** — AI predicted UP/DOWN **4–5s before close**, bought the predicted side, redeemed at **$1** |
| **What changed** | After Polymarket’s **TWAP price update**, the endcycle sniper **no longer produces reliable profit** |
| **Current strategy** | **HFT MM** — high-frequency market making across the full interval; **not impacted by TWAP or other settlement changes** |

The endcycle approach relied on late-cycle mispricing against the settlement reference. TWAP removed that edge. **HFT MM** earns from spread capture and continuous two-sided flow instead — logic that does not depend on how the final reference price is computed.

---

## How it works

Polymarket runs rolling **N-minute** crypto markets (typically **5m**):

- **Strike / price to beat** = reference price at interval **start**
- **UP** wins if price at **end** is **above** the strike
- **DOWN** wins if price at **end** is **below** the strike
- Winning shares redeem at **~$1**; losers → **$0**

```
Interval (e.g. 5 minutes)
|-----------------------------------------------------------|
start                                                  end
     │  post UP bid / ask ────┐
     │  post DOWN bid / ask ──┤  HFT MM loop (full interval)
     │  refresh on book move ─┤
     │  rebalance inventory ──┘
     └─ capture spread → merge / redeem → next market
```

### HFT MM loop

| Step | Action |
|------|--------|
| 1 | Discover the active Up/Down market for the configured asset / interval |
| 2 | Stream spot (Coinbase / Binance / Chainlink) and CLOB book updates |
| 3 | Post two-sided quotes on UP and DOWN tokens |
| 4 | Refresh quotes at high frequency as price and inventory shift |
| 5 | Rebalance inventory after resolution; roll to the next interval |

Skip or size down when the book has no liquidity, latency is too high, or paper mode is on.

### Why HFT MM survives platform changes

| Endcycle Sniper (deprecated) | HFT MM (active) |
|------------------------------|-----------------|
| Edge from predicting direction **seconds before close** | Edge from **spread capture** across the full interval |
| TWAP changed final reference pricing | Quoting logic is **independent of settlement reference** |
| Late-cycle mispricing → **no reliable profit** | Two-sided flow and inventory rotation → **unchanged by updates** |

---

## Features

- **High-frequency market making** — continuous bid/ask quoting, not end-of-cycle sniping
- **Fast order refresh** — reacts to book and spot moves in real time
- Live spot + CLOB feeds for quote pricing
- Multi-asset Up/Down markets (BTC, ETH, SOL, …)
- Inventory management — merge and redeem after resolution
- Paper trading mode for safe testing

---

## Parameters

Set in [`src/config/params.py`](src/config/params.py) or `.env`:

| Param | Role |
|-------|------|
| `ORDER_SIZE` | Quote / order size |
| `BUY_LIMIT_PRICE` | Max buy price when crossing the book |
| `SELL_LIMIT_PRICE` | Min sell price when dumping inventory |
| `MIN_PLACE_INTERVAL_SEC` | Minimum interval between order placements |
| `MARKET_INTERVAL_SECONDS` | Interval length (default `300` = 5m) |
| `ASSET` / `MARKET_SLUG_PREFIX` | Which Up/Down series to follow |
| `PAPER_TRADING` | `1` = simulate, `0` = live |

```bash
# .env — fill before live trading
PRIVATE_KEY=
FUNDER=
ORDER_SIZE=30
BUY_LIMIT_PRICE=0.99
SELL_LIMIT_PRICE=0.01
ASSET=btc
MARKET_INTERVAL_SECONDS=300
PAPER_TRADING=1
```

---

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# edit .env — set PRIVATE_KEY, FUNDER, and HFT MM params
python main.py
```

**Config files**

- Tunables: [`src/config/params.py`](src/config/params.py)
- Runtime state: [`src/config/config.py`](src/config/config.py)
- Env template: [`.env.example`](.env.example)

---

## Links

- **Telegram:** [@dizzy](https://t.me/dizzy283)
- **Polymarket:** [@flippingsharks](https://polymarket.com/@flippingsharks)
- **Wallet:** [0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4](https://polymarket.com/profile/0xc387c2a40d389f17b723b6bba9b18b7dbd2de4f4)
