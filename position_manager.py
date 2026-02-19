#!/usr/bin/env python3
"""
Position Manager Bot - Automated position management for Polymarket BTC 5-min markets

Flow:
1. START MARKET
2. CHECK BALANCE
   - [Insufficient] → STOP BOT
   - [Enough] → Continue
3. CHECK POSITIONS LOOP
   - [Equal Shares] → MERGE → NEXT MARKET
   - [Not Equal]
     - [30s before close?] → FORCE SELL → NEXT MARKET
     - [No] → WAIT 60s → RECHECK
"""

import os
import time
from datetime import datetime
from typing import Optional, Dict, Any

# Try to load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    print("Warning: web3.py not installed. Install with: pip install web3")

from polymarket_bot import PolymarketBot


def format_time(seconds: int) -> str:
    """Format seconds into readable time string"""
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}m {secs}s"


def get_balance(address: str) -> float:
    """
    Get USDC balance for a wallet address using Polygon RPC
    Equivalent to the reference TypeScript function
    
    Args:
        address: Wallet address to check balance for
        
    Returns:
        USDC balance as float
    """
    if not WEB3_AVAILABLE:
        print("⚠️  web3.py not available. Cannot check balance.")
        return 0.0
    
    try:
        # Get Polygon RPC URL from environment
        RPC_URL = os.getenv(
            "POLYGON_RPC",
            "https://go.getblock.us/f3ba334a60f1446c9289381e569b2634"
        )
        
        # USDC contract address on Polygon
        USDC_CONTRACT_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
        
        # USDC ERC20 ABI (minimal - just balanceOf)
        USDC_ABI = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        # Create RPC provider (equivalent to ethers JsonRpcProvider)
        rpc_provider = Web3(Web3.HTTPProvider(RPC_URL))
        
        if not rpc_provider.is_connected():
            print(f"⚠️  Failed to connect to Polygon RPC: {RPC_URL}")
            return 0.0
        
        # Create USDC contract instance (equivalent to ethers.Contract)
        usdc_contract = rpc_provider.eth.contract(
            address=Web3.to_checksum_address(USDC_CONTRACT_ADDRESS),
            abi=USDC_ABI
        )
        
        # Get balance (equivalent to contract.balanceOf(address))
        balance_usdc = usdc_contract.functions.balanceOf(
            Web3.to_checksum_address(address)
        ).call()
        
        # Format units with 6 decimals (equivalent to ethers.utils.formatUnits(balance, 6))
        balance_usdc_real = balance_usdc / (10 ** 6)
        
        # Return as float (equivalent to parseFloat)
        return float(balance_usdc_real)
        
    except Exception as e:
        print(f"⚠️  Error getting balance: {e}")
        import traceback
        traceback.print_exc()
        return 0.0


def check_balance_sufficient(bot: PolymarketBot, min_balance: float = 0.01) -> bool:
    """
    Check if account has sufficient USDC balance using Polygon RPC
    
    Args:
        bot: PolymarketBot instance
        min_balance: Minimum required balance in USDC
        
    Returns:
        True if balance is sufficient, False otherwise
    """
    if not bot.private_key:
        print("⚠️  Private key not available. Cannot check balance.")
        return True
    
    try:
        # Get wallet address from private key
        if not WEB3_AVAILABLE:
            print("⚠️  web3.py not available. Cannot check balance via RPC.")
            print("⚠️  Assuming sufficient balance. Install web3: pip install web3")
            return True
        funder = os.getenv("FUNDER")
        print(f"📧 Wallet address: {funder}")
        
        # Get balance using the reference function pattern
        balance_float = get_balance(funder)
        
        print(f"💰 USDC Balance: {balance_float:.4f}")
        min_balance = float(os.getenv("ORDER_PRICE")) * float(os.getenv("ORDER_SIZE")) * 2
        print(f"💰 Min balance: {min_balance:.4f}")
        if balance_float < min_balance:
            print(f"❌ Insufficient balance: {balance_float:.4f} < {min_balance:.4f}")
            return False
        
        print(f"✅ Sufficient balance: {balance_float:.4f} >= {min_balance:.4f}")
        return True
        
    except Exception as e:
        print(f"⚠️  Error checking balance: {e}")
        import traceback
        traceback.print_exc()
        # Assume sufficient if we can't check
        print("⚠️  Assuming sufficient balance due to error.")
        return True


def are_positions_equal(positions: Dict[str, float], tolerance: float = 0.01) -> bool:
    """
    Check if UP and DOWN positions are approximately equal
    
    Args:
        positions: Dictionary with 'up_balance' and 'down_balance'
        tolerance: Maximum difference to consider equal
        
    Returns:
        True if positions are equal within tolerance
    """
    up = positions.get("up_balance", 0.0)
    down = positions.get("down_balance", 0.0)
    
    diff = abs(up - down)
    return diff <= tolerance


def get_min_position(positions: Dict[str, float]) -> float:
    """Get the minimum of UP and DOWN positions"""
    up = positions.get("up_balance", 0.0)
    down = positions.get("down_balance", 0.0)
    return min(up, down)


def is_near_market_close(bot: PolymarketBot, market: Dict[Any, Any], seconds_before: int = 30) -> bool:
    """
    Check if market is closing within specified seconds
    
    Args:
        bot: PolymarketBot instance
        market: Market data dictionary
        seconds_before: How many seconds before close to trigger
        
    Returns:
        True if market closes within seconds_before
    """
    close_time = bot.get_market_close_time(market)
    if not close_time:
        # If we can't determine close time, assume not close
        return False
    
    current_time = bot.get_current_timestamp()
    time_until_close = close_time - current_time
    
    return time_until_close <= seconds_before


def process_market(bot: PolymarketBot, market: Dict[Any, Any], token_ids: Dict[str, str]) -> bool:
    """
    Process a single market according to the flow
    
    Args:
        bot: PolymarketBot instance
        market: Market data dictionary
        token_ids: Dictionary with 'up_token_id' and 'down_token_id'
        
    Returns:
        True if should continue to next market, False if should stop
    """
    print("\n" + "="*60)
    print(f"📊 Processing Market")
    print("="*60)
    
    # Check balance
    print("\n1️⃣  Checking balance...")
    if not check_balance_sufficient(bot):
        print("\n❌ Insufficient balance. Stopping bot.")
        return False
    
    # Get market close time
    close_time = bot.get_market_close_time(market)
    if close_time:
        close_dt = datetime.fromtimestamp(close_time)
        print(f"⏰ Market closes at: {close_dt.strftime('%H:%M:%S')}")
    
    # Position check loop
    print("\n2️⃣  Entering position check loop...")
    iteration = 0
    
    while True:
        iteration += 1
        current_time = bot.get_current_timestamp()
        
        if close_time:
            time_until_close = close_time - current_time
            if time_until_close > 0:
                print(f"\n⏱️  Time until close: {format_time(time_until_close)}")
            else:
                print(f"\n⏱️  Market has closed")
        
        # Check positions
        print(f"\n📈 Checking positions (iteration {iteration})...")

        positions = bot.get_positions(token_ids)

        
        # Check if positions are equal
        if are_positions_equal(positions):
            print("\n✅ Positions are equal! Merging tokens...")
            min_pos = get_min_position(positions)
            
            if min_pos > 0:
                result = bot.merge_tokens(token_ids, min_pos)
                if result:
                    print(f"✅ Successfully merged {min_pos:.6f} tokens")
                    print("\n➡️  Moving to next market...")
                    # Get order parameters from environment
                    order_price = float(os.getenv("ORDER_PRICE", "0.46"))
                    order_size = float(os.getenv("ORDER_SIZE", "5.0"))
                    
                    next_market = bot.find_next_active_market()
                    if next_market:
                        next_token_ids = bot.get_token_ids(next_market)
                        if next_token_ids:
                            print(f"\n📋 Placing limit orders for next epoch market...")
                            print(f"  Price: {order_price}, Size: {order_size}")
                            up_order = bot.place_limit_order_up(
                                token_ids=next_token_ids,
                                price=order_price,
                                size=order_size,
                                side="BUY"
                            )
                            down_order = bot.place_limit_order_down(
                                token_ids=next_token_ids,
                                price=order_price,
                                size=order_size,
                                side="BUY"
                            )
                            if up_order or down_order:
                                print("✅ Orders placed for next market")
                            else:
                                print("⚠️  Failed to place orders for next market")
                            return True
                        else:
                            print("❌ Could not extract token IDs from next market. Moving to next market...")
                            return True
                    else:
                        print("❌ Could not find next market. Moving to next market...")
                        return True    
                else:
                    print("❌ Merge failed. Retrying in 60s...")
                    time.sleep(60)
                    continue
            else:
                print("ℹ️  No positions to merge. Moving to next market...")
                return True
        
        # Positions are not equal
        print("\n⚠️  Positions are not equal")
        
        # Check if 30s before close
        if is_near_market_close(bot, market, seconds_before=30):
            print("⏰ Market closes in 30s or less. Force selling all positions...")
            results = bot.force_sell_all(token_ids)
            
            up_sold = results["up_order"] is not None
            down_sold = results["down_order"] is not None
            
            if up_sold or down_sold:
                print("✅ Force sell completed")
            else:
                print("⚠️  No positions to sell")
            
            print("\n➡️  Moving to next market...")
            # Place orders for next epoch market
            # Get order parameters from environment
            order_price = float(os.getenv("ORDER_PRICE", "0.46"))
            order_size = float(os.getenv("ORDER_SIZE", "5.0"))
            
            next_market = bot.find_next_active_market()
            if next_market:
                next_token_ids = bot.get_token_ids(next_market)
                if next_token_ids:
                    print(f"\n📋 Placing limit orders for next epoch market...")
                    print(f"  Price: {order_price}, Size: {order_size}")
                    up_order = bot.place_limit_order_up(
                        token_ids=next_token_ids,
                        price=order_price,
                        size=order_size,
                        side="BUY"
                    )
                    down_order = bot.place_limit_order_down(
                        token_ids=next_token_ids,
                        price=order_price,
                        size=order_size,
                        side="BUY"
                    )
                    if up_order or down_order:
                        print("✅ Orders placed for next market")
                    else:
                        print("⚠️  Failed to place orders for next market")
                    return True
                else:
                    print("❌ Could not extract token IDs from next market. Moving to next market...")
                    return True
            else:
                print("❌ Could not find next market. Moving to next market...")
                return True
        
        # Wait 60s and recheck
        print("⏳ Waiting 60s before rechecking...")
        time.sleep(60)


def main():
    """Main function for position management bot"""
    
    # Load configuration
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        print("❌ ERROR: PRIVATE_KEY not set. Export it or add to .env")
        return
    
    host = os.getenv("HOST", "https://clob.polymarket.com")
    funder = os.getenv("FUNDER")
    chain_id = os.getenv("CHAIN_ID")
    signature_type = os.getenv("SIGNATURE_TYPE")
    
    # Initialize bot
    print("🤖 Initializing Position Manager Bot...")
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
    
    print("✅ Bot initialized successfully\n")
    
    # Main loop: process markets continuously
    market_count = 0
    
    try:
        while True:
            market_count += 1
            print("\n" + "="*60)
            print(f"🚀 START MARKET #{market_count}")
            print("="*60)
            
            # Find current market
            print("\n🔍 Finding current BTC 5-min market...")
            market = bot.find_current_market()
            
            if not market:
                print("❌ Could not find active market. Waiting 30s...")
                time.sleep(30)
                continue
            
            # Get token IDs
            token_ids = bot.get_token_ids(market)
            if not token_ids:
                print("❌ Could not extract token IDs. Waiting 30s...")
                time.sleep(30)
                continue
            
            print(f"✅ Market found")
            print(f"  UP token:  {token_ids['up_token_id']}")
            print(f"  DOWN token: {token_ids['down_token_id']}")
            
            # Process market
            should_continue = process_market(bot, market, token_ids)
            
            if not should_continue:
                print("\n🛑 Bot stopped due to insufficient balance or error")
                break
            
            # Wait a bit before moving to next market
            print("\n⏳ Waiting 10s before checking next market...")
            time.sleep(10)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

