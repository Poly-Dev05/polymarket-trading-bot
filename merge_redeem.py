#!/usr/bin/env python3
"""
Merge and Redeem Script for Polymarket BTC 5-min markets
- Merge: Combine 1.0 UP + 1.0 DOWN tokens to get 1.0 USDC
- Redeem: Redeem winning tokens after market resolution
"""

import os
import sys
from typing import Optional, Dict, Any

# Try to load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from polymarket_bot import PolymarketBot


def check_balances(bot: PolymarketBot, token_ids: Dict[str, str]) -> Dict[str, float]:
    """
    Check balances for UP and DOWN tokens
    
    Args:
        bot: PolymarketBot instance
        token_ids: Dictionary with 'up_token_id' and 'down_token_id'
        
    Returns:
        Dictionary with 'up_balance' and 'down_balance'
    """
    if not bot.client:
        print("❌ CLOB client not initialized")
        return {"up_balance": 0.0, "down_balance": 0.0}
    
    try:
        up_token = token_ids.get("up_token_id")
        down_token = token_ids.get("down_token_id")
        
        if not up_token or not down_token:
            print("❌ Token IDs not found")
            return {"up_balance": 0.0, "down_balance": 0.0}
        
        # Get balances using CLOB client
        up_balance = bot.client.get_balance(up_token)
        down_balance = bot.client.get_balance(down_token)
        
        return {
            "up_balance": float(up_balance) if up_balance else 0.0,
            "down_balance": float(down_balance) if down_balance else 0.0
        }
    except Exception as e:
        print(f"❌ Error checking balances: {e}")
        import traceback
        traceback.print_exc()
        return {"up_balance": 0.0, "down_balance": 0.0}


def merge_tokens(
    bot: PolymarketBot,
    token_ids: Dict[str, str],
    amount: Optional[float] = None
) -> Optional[Dict[Any, Any]]:
    """
    Merge UP and DOWN tokens to get USDC back
    Requires: 1.0 UP token + 1.0 DOWN token = 1.0 USDC
    
    Args:
        bot: PolymarketBot instance
        token_ids: Dictionary with 'up_token_id' and 'down_token_id'
        amount: Amount to merge (default: minimum of available balances)
        
    Returns:
        Transaction response or None if failed
    """
    if not bot.client:
        print("❌ CLOB client not initialized")
        return None
    
    try:
        # Check balances first
        balances = check_balances(bot, token_ids)
        up_balance = balances["up_balance"]
        down_balance = balances["down_balance"]
        
        print(f"\n📊 Current balances:")
        print(f"  UP token: {up_balance:.6f}")
        print(f"  DOWN token: {down_balance:.6f}")
        
        # Determine merge amount
        if amount is None:
            amount = min(up_balance, down_balance)
        
        if amount <= 0:
            print("❌ Insufficient balance to merge")
            return None
        
        if up_balance < amount or down_balance < amount:
            print(f"❌ Insufficient balance. Need {amount:.6f} of each token")
            print(f"   Available: UP={up_balance:.6f}, DOWN={down_balance:.6f}")
            return None
        
        print(f"\n🔄 Merging {amount:.6f} UP + {amount:.6f} DOWN tokens...")
        
        # Use CLOB client merge function if available
        # Note: The exact method name may vary depending on py-clob-client version
        try:
            # Try merge_positions method
            if hasattr(bot.client, 'merge_positions'):
                result = bot.client.merge_positions(
                    token_ids['up_token_id'],
                    token_ids['down_token_id'],
                    amount
                )
            # Try merge method
            elif hasattr(bot.client, 'merge'):
                result = bot.client.merge(
                    token_ids['up_token_id'],
                    token_ids['down_token_id'],
                    amount
                )
            else:
                print("❌ Merge function not available in CLOB client")
                print("   You may need to use web3.py to interact with conditional token contracts directly")
                return None
            
            print(f"✅ Merge successful: {result}")
            return result
            
        except AttributeError:
            print("❌ Merge function not found in CLOB client")
            print("   Consider using web3.py to interact with conditional token contracts")
            return None
            
    except Exception as e:
        print(f"❌ Error merging tokens: {e}")
        import traceback
        traceback.print_exc()
        return None


def redeem_tokens(
    bot: PolymarketBot,
    token_ids: Dict[str, str],
    outcome: str = "UP"
) -> Optional[Dict[Any, Any]]:
    """
    Redeem winning tokens after market resolution
    
    Args:
        bot: PolymarketBot instance
        token_ids: Dictionary with 'up_token_id' and 'down_token_id'
        outcome: "UP" or "DOWN" - which token won
        
    Returns:
        Transaction response or None if failed
    """
    if not bot.client:
        print("❌ CLOB client not initialized")
        return None
    
    if outcome.upper() not in ["UP", "DOWN"]:
        print(f"❌ Invalid outcome '{outcome}'. Must be 'UP' or 'DOWN'")
        return None
    
    try:
        winning_token = token_ids.get(f"{outcome.lower()}_token_id")
        if not winning_token:
            print(f"❌ {outcome} token ID not found")
            return None
        
        # Check balance
        balances = check_balances(bot, token_ids)
        balance = balances[f"{outcome.lower()}_balance"]
        
        if balance <= 0:
            print(f"❌ No {outcome} tokens to redeem (balance: {balance:.6f})")
            return None
        
        print(f"\n💰 Redeeming {balance:.6f} {outcome} tokens...")
        
        # Use CLOB client redeem function if available
        try:
            if hasattr(bot.client, 'redeem'):
                result = bot.client.redeem(winning_token, balance)
            elif hasattr(bot.client, 'redeem_position'):
                result = bot.client.redeem_position(winning_token, balance)
            else:
                print("❌ Redeem function not available in CLOB client")
                print("   You may need to use web3.py to interact with conditional token contracts directly")
                return None
            
            print(f"✅ Redeem successful: {result}")
            return result
            
        except AttributeError:
            print("❌ Redeem function not found in CLOB client")
            print("   Consider using web3.py to interact with conditional token contracts")
            return None
            
    except Exception as e:
        print(f"❌ Error redeeming tokens: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    """Main function for merge/redeem operations"""
    
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
    
    # Find current market
    print("\n🔍 Finding current BTC 5-min market...")
    market = bot.find_current_market()
    
    if not market:
        print("❌ Could not find active BTC up/down 5-minute market")
        return
    
    # Get token IDs
    token_ids = bot.get_token_ids(market)
    if not token_ids:
        print("❌ Could not extract token IDs from market data")
        return
    
    print(f"\n📋 Token IDs:")
    print(f"  UP: {token_ids['up_token_id']}")
    print(f"  DOWN: {token_ids['down_token_id']}")
    
    # Check balances
    print("\n" + "="*60)
    balances = check_balances(bot, token_ids)
    print(f"UP balance: {balances['up_balance']:.6f}")
    print(f"DOWN balance: {balances['down_balance']:.6f}")
    print("="*60)
    
    # Interactive menu
    while True:
        print("\n📋 Options:")
        print("  1. Merge tokens (1.0 UP + 1.0 DOWN = 1.0 USDC)")
        print("  2. Redeem UP tokens")
        print("  3. Redeem DOWN tokens")
        print("  4. Check balances")
        print("  5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            amount_str = input("Enter amount to merge (or press Enter for max): ").strip()
            amount = float(amount_str) if amount_str else None
            merge_tokens(bot, token_ids, amount)
            
        elif choice == "2":
            redeem_tokens(bot, token_ids, "UP")
            
        elif choice == "3":
            redeem_tokens(bot, token_ids, "DOWN")
            
        elif choice == "4":
            balances = check_balances(bot, token_ids)
            print(f"\n📊 Current balances:")
            print(f"  UP: {balances['up_balance']:.6f}")
            print(f"  DOWN: {balances['down_balance']:.6f}")
            
        elif choice == "5":
            print("👋 Exiting...")
            break
            
        else:
            print("❌ Invalid option. Please select 1-5.")


if __name__ == "__main__":
    main()

