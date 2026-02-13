"""
Main entry point for Polymarket Trading Bot
"""
import os
from datetime import datetime

# Try to load from .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, will only use environment variables

from polymarket_bot import PolymarketBot


def main():
    """Main function to test the bot and place orders"""
    # Load private key from environment variable or .env file
    private_key = os.getenv("PRIVATE_KEY")
    
    if not private_key:
        print("=" * 60)
        print("ERROR: PRIVATE_KEY not found!")
        print("=" * 60)
        print("\nTo set your private key, use one of these methods:")
        print("\n1. Environment variable:")
        print("   export PRIVATE_KEY=your_private_key_here")
        print("\n2. Create a .env file in the project directory:")
        print("   echo 'PRIVATE_KEY=your_private_key_here' > .env")
        print("\n3. Or install python-dotenv and create .env file:")
        print("   pip install python-dotenv")
        print("   Then create .env file with: PRIVATE_KEY=your_private_key_here")
        print("=" * 60)
        return
    
    # Check if private key looks valid (should start with 0x and be 66 chars for hex)
    if not private_key.startswith("0x"):
        print("Warning: Private key should start with '0x'")
    elif len(private_key) != 66:
        print(f"Warning: Private key length is {len(private_key)}, expected 66 characters (0x + 64 hex chars)")
    
    print(f"Private key loaded: {private_key[:10]}...{private_key[-10:]}")
    
    # Load configuration from environment
    host = os.getenv("HOST", "https://clob.polymarket.com")
    funder = os.getenv("FUNDER")
    chain_id = os.getenv("CHAIN_ID")
    signature_type = os.getenv("SIGNATURE_TYPE")
    
    # Convert chain_id to integer if provided

    print(f"Host: {host}")
    print(f"Funder: {funder}")
    print(f"Chain ID: {chain_id}")
    print(f"Signature Type: {signature_type}")
    
    # Initialize bot with private key
    bot = PolymarketBot(
        host=host,
        private_key=private_key,
        funder=funder,
        chain_id=chain_id,
        signature_type=signature_type
    )
    
    # Verify CLOB client was initialized
    if not bot.client:
        print("\n" + "=" * 60)
        print("ERROR: CLOB client failed to initialize!")
        print("=" * 60)
        print("Please check:")
        print("1. py-clob-client is installed: pip install py-clob-client")
        print("2. Private key is valid and properly formatted")
        print("3. All required parameters are set correctly")
        print("=" * 60)
        return
    
    # Get current timestamp
    current_ts = bot.get_current_timestamp()
    print(f"Current timestamp: {current_ts}")
    print(f"Current time: {datetime.fromtimestamp(current_ts)}")
    
    # Calculate the active market timestamp (rounded up to next 5-minute interval)
    market_timestamp = ((current_ts + 299) // 300) * 300
    print(f"Next Active market timestamp: {market_timestamp}")
    print(f"Next Active market time: {datetime.fromtimestamp(market_timestamp)}")
    
    # Generate slug for active market
    slug = bot.generate_slug(market_timestamp)
    print(f"Generated slug: {slug}")
    
    # Try to find active market
    print("\nSearching for active market...")
    market = bot.find_next_active_market()
    
    if market:
        print(f"\nMarket found!")
        
        # Get Up and Down token IDs from the market object
        print("\nExtracting token IDs from market...")
        token_ids = bot.get_token_ids(market)
        
        if token_ids:
            print(f"Token IDs extracted:")
            print(f"  Up token ID: {token_ids.get('up_token_id')}")
            print(f"  Down token ID: {token_ids.get('down_token_id')}")
            
            # Place orders for both Up and Down tokens
            price = float(os.getenv("ORDER_PRICE", "0.46"))
            size = float(os.getenv("ORDER_SIZE", "5.0"))
            
            print(f"\nPlacing orders:")
            print(f"  Price: {price}")
            print(f"  Size: {size} tokens each")
            
            # Place order for Up token
            print(f"\nPlacing BUY order for Up token...")
            up_order = bot.place_limit_order_up(
                token_ids=token_ids,
                price=price,
                size=size,
                side="BUY"
            )
            
            if up_order:
                print(f"✓ Up token order placed successfully")
            else:
                print(f"✗ Failed to place Up token order")
            
            # Place order for Down token
            print(f"\nPlacing BUY order for Down token...")
            down_order = bot.place_limit_order_down(
                token_ids=token_ids,
                price=price,
                size=size,
                side="BUY"
            )
            
            if down_order:
                print(f"✓ Down token order placed successfully")
            else:
                print(f"✗ Failed to place Down token order")
            
            print(f"\nOrder placement complete!")
        else:
            print("Could not extract token IDs from market data")
    else:
        print("\nNo Next active market found. This might be normal if:")
        print("- The market hasn't started yet")
        print("- The API endpoint structure is different")
        print("- Authentication is required")


if __name__ == "__main__":
    main()
