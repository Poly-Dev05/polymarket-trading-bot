# Polymarket BTC 5-Minute Trading Bot

🤖 Automated trading bot for Polymarket BTC 5-minute up/down markets. Trade 24/7 with automated position management and risk controls.

[![Polymarket 5min Trading Bot](https://img.youtube.com/vi/DLhBdoVSUmk/maxresdefault.jpg)](https://www.youtube.com/watch?v=teeMT-c4S3o=1)

📹 **Demo Video**: [Watch on YouTube](https://www.youtube.com/watch?v=teeMT-c4S3o)

## 📸 Screenshot

![Bot interface](image.png)

*Bot interface showing real-time trading on Polymarket BTC 5-minute up/down market with position management console*

## ✨ Features

- 🔍 **Auto Market Discovery** - Finds active BTC 5-minute markets automatically
- 📊 **Smart Position Management** - Monitors and balances UP/DOWN positions
- 🛡️ **Risk Protection** - Auto-sells before market close to prevent losses
- ⚡ **Continuous Trading** - Runs across multiple 5-minute market epochs
- 💰 **Token Merging** - Automatically recovers USDC from equal positions

## 🚀 Quick Start

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure `.env` file:**
```bash
PRIVATE_KEY=0x...              # Your wallet private key
ORDER_PRICE=0.46               # Limit order price
ORDER_SIZE=5.0                 # Order size
```

3. **Run the bot:**
```bash
python main.py
```

## 📋 How It Works

The bot continuously:
1. Finds the current BTC 5-minute market
2. Monitors UP/DOWN token positions
3. Merges equal positions to recover USDC
4. Force sells before market close (30s threshold)
5. Places orders for the next market automatically

## 🔧 Configuration

Key environment variables:
- `PRIVATE_KEY` - Wallet private key (required)
- `ORDER_PRICE` - Limit order price (default: 0.46)
- `ORDER_SIZE` - Order size (default: 5.0)
- `HOST` - CLOB API host (default: https://clob.polymarket.com)

## ⚠️ Security

Never commit your `.env` file or private key. Keep credentials secure.

## 📚 Documentation

See `WORKFLOW.md` for detailed workflow and `polymarket_bot_v1.py` for API reference.

## 📞 Contact

- **Telegram**: [S.E.I](https://t.me/sei_dev)

