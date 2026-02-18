

# Workflow and roadmap

## Complete workflow diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    BOT INITIALIZATION                        │
│  • Load PRIVATE_KEY, HOST, CHAIN_ID, etc. from .env         │
│  • Initialize PolymarketBot with CLOB client                │
│  • Verify client initialization                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    MAIN LOOP (Infinite)                      │
│  Market Count: #1, #2, #3, ...                              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 1: FIND CURRENT MARKET                     │
│  • Call bot.find_current_market()                           │
│  • Get BTC 5-min market for current epoch                   │
│  • Extract UP and DOWN token IDs                            │
│  • If not found → Wait 30s → Retry                         │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 2: PROCESS MARKET                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 2.1: CHECK BALANCE                                     │  │
│  │  • Check USDC balance                                 │  │
│  │  • If insufficient → STOP BOT ❌                      │  │
│  │  • If sufficient → Continue ✅                        │  │
│  └──────────────────────┬─────────────────────────────────┘  │
│                         │                                     │
│                         ▼                                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 2.2: POSITION CHECK LOOP (Continuous)                 │  │
│  │                                                        │  │
│  │  ┌──────────────────────────────────────────────┐    │  │
│  │  │ Check UP and DOWN token balances              │    │  │
│  │  │ Display: UP balance, DOWN balance, Difference│    │  │
│  │  └──────────────┬───────────────────────────────┘    │  │
│  │                 │                                      │  │
│  │                 ▼                                      │  │
│  │  ┌──────────────────────────────────────────────┐    │  │
│  │  │ Are positions EQUAL? (within 0.01 tolerance) │    │  │
│  │  └──────┬───────────────────────┬─────────────────┘    │  │
│  │         │ YES                  │ NO                    │  │
│  │         ▼                      ▼                       │  │
│  │  ┌──────────────┐    ┌──────────────────────────┐   │  │
│  │  │ MERGE PATH   │    │ CHECK TIME TO CLOSE       │   │  │
│  │  │              │    │                           │   │  │
│  │  │ • Merge equal │    │ • Is 30s before close?    │   │  │
│  │  │   tokens     │    │   ┌────────┬──────────┐   │   │  │
│  │  │ • Get min    │    │   │ YES    │ NO      │   │   │  │
│  │  │   position   │    │   ▼        ▼         │   │   │  │
│  │  │ • Call       │    │ ┌──────┐ ┌────────┐ │   │   │  │
│  │  │   merge_tokens│  │ │FORCE │ │ WAIT 60s│ │   │   │  │
│  │  │              │    │ │SELL  │ │ RECHECK │ │   │   │  │
│  │  │ If success:  │    │ └──┬───┘ └────┬────┘ │   │   │  │
│  │  │   → NEXT     │    │    │          │      │   │   │  │
│  │  │   MARKET     │    │    │          └──────┼───┘   │  │
│  │  │              │    │    │                 │       │  │
│  │  │ If fail:     │    │    │                 │       │  │
│  │  │   → Wait 60s │    │    │                 │       │  │
│  │  │   → Retry    │    │    │                 │       │  │
│  │  └──────┬───────┘    │    │                 │       │  │
│  │         │            │    │                 │       │  │
│  │         └────────────┴────┴─────────────────┘       │  │
│  │                    │                                  │  │
│  │                    ▼                                  │  │
│  │         ┌───────────────────────────┐                  │  │
│  │         │ PLACE ORDERS FOR NEXT     │                  │  │
│  │         │ EPOCH MARKET              │                  │  │
│  │         │                           │                  │  │
│  │         │ • Find next market        │                  │  │
│  │         │ • Get ORDER_PRICE,        │                  │  │
│  │         │   ORDER_SIZE from .env    │                  │  │
│  │         │ • Place BUY limit order   │                  │  │
│  │         │   for UP token            │                  │  │
│  │         │ • Place BUY limit order   │                  │  │
│  │         │   for DOWN token           │                  │  │
│  │         └───────────┬───────────────┘                  │  │
│  │                     │                                   │  │
│  │                     ▼                                   │  │
│  │         ┌───────────────────────────┐                  │  │
│  │         │ RETURN TO MAIN LOOP       │                  │  │
│  │         │ (Continue to next market)  │                  │  │
│  │         └───────────────────────────┘                  │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              STEP 3: WAIT & CONTINUE                         │
│  • Wait 10s before checking next market                     │
│  • Loop back to STEP 1 (Find next market)                   │
│  • Market count increments                                  │
└─────────────────────────────────────────────────────────────┘
```

## Detailed step-by-step workflow

### Phase 1: Initialization
1. Load environment variables:
   - `PRIVATE_KEY` (required)
   - `HOST` (default: "https://clob.polymarket.com")
   - `FUNDER`, `CHAIN_ID`, `SIGNATURE_TYPE` (optional)
   - `ORDER_PRICE` (default: 0.46)
   - `ORDER_SIZE` (default: 5.0)
2. Initialize `PolymarketBot` with CLOB client
3. Verify client initialization

### Phase 2: Main loop (continuous)
For each market epoch:

#### Step 1: Market discovery
- Find current BTC 5-minute market using `find_current_market()`
- Extract UP and DOWN token IDs
- If not found: wait 30s and retry

#### Step 2: Market processing

##### 2.1: Balance check
- Check USDC balance
- If insufficient (< 0.01): stop bot
- If sufficient: continue

##### 2.2: Position monitoring loop

Iteration flow:
1. Check positions:
   - Get UP token balance
   - Get DOWN token balance
   - Calculate difference
   - Display all values
2. Decision tree:

   Path A: Positions are equal (within 0.01 tolerance)
   - Merge tokens:
     - Get minimum of UP/DOWN balances
     - Call `merge_tokens()` with min position
     - If success:
       - Find next epoch market
       - Place limit orders for next market (ORDER_PRICE, ORDER_SIZE)
       - Return to main loop
     - If fail:
       - Wait 60s
       - Retry merge

   Path B: Positions are not equal
   - Check time until market close:
     - If ≤ 30 seconds:
       - Force sell all positions (market orders)
       - Find next epoch market
       - Place limit orders for next market
       - Return to main loop
     - If > 30 seconds:
       - Wait 60s
       - Recheck positions (loop back)

#### Step 3: Transition to next market
- Wait 10s
- Increment market count
- Loop back to Step 1

## Key functions and their roles

| Function | Purpose |
|----------|---------|
| `check_balance_sufficient()` | Validates USDC balance before trading |
| `are_positions_equal()` | Checks if UP/DOWN positions are balanced (tolerance: 0.01) |
| `get_min_position()` | Gets minimum of UP/DOWN for merging |
| `is_near_market_close()` | Checks if market closes within 30s |
| `process_market()` | Main market processing logic |
| `bot.merge_tokens()` | Merges equal UP/DOWN tokens to get USDC back |
| `bot.force_sell_all()` | Sells all positions using market orders |
| `bot.find_next_active_market()` | Finds the next epoch market |
| `bot.place_limit_order_up/down()` | Places limit orders for next market |

## Environment variables

```bash
# Required
PRIVATE_KEY=0x...              # Your wallet private key

# Optional (with defaults)
HOST=https://clob.polymarket.com
ORDER_PRICE=0.46               # Price for limit orders
ORDER_SIZE=5.0                 # Size for limit orders
FUNDER=                        # Optional funder address
CHAIN_ID=                      # Optional chain ID
SIGNATURE_TYPE=                # Optional signature type
```

## Decision points

1. Balance check: insufficient → stop bot
2. Position equality: equal → merge path
3. Position inequality: check time to close
4. Time to close: ≤30s → force sell; >30s → wait and recheck
5. Merge success: place orders for next market
6. Force sell: place orders for next market

## Error handling

- Market not found: wait 30s, retry
- Token IDs not found: wait 30s, retry
- Merge failed: wait 60s, retry
- Order placement failed: log warning, continue
- Insufficient balance: stop bot
- Keyboard interrupt (Ctrl+C): graceful shutdown

## Expected behavior

1. Continuous operation across 5-minute market epochs
2. Automatic position management (merge when equal, sell before close)
3. Proactive order placement for the next market
4. Risk management (balance checks, force sell before close)
5. Resilient to temporary failures (retries, continues on errors)

## Timeline example

```
00:00 - Market #1 starts
00:00 - Check balance ✅
00:00 - Check positions (UP: 0, DOWN: 0)
00:01 - Wait 60s...
00:02 - Check positions (UP: 5.0, DOWN: 4.8) - Not equal
00:03 - Wait 60s...
...
04:30 - Check positions (UP: 5.0, DOWN: 5.0) - Equal!
04:30 - Merge tokens ✅
04:30 - Place orders for Market #2
04:30 - Return to main loop
04:30 - Wait 10s
04:40 - Market #2 starts (orders already placed)
...
```

This bot runs continuously, managing positions and placing orders for the next market automatically.