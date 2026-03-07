# Polymarket BTC 5 分钟交易机器人

**🌐 语言 / Language:** [English](README.md) | [中文](README.zh-CN.md)

**📞 联系方式：** [S.E.I](https://t.me/sei_dev)（Telegram）

---

🤖 Polymarket BTC 5 分钟涨跌市场自动交易机器人，7×24 小时运行，支持三种策略：

| 策略 | 描述 | 机器人 |
|------|------|--------|
| **策略 1** | 市场中段套利 | [@sei_arb_bot](https://t.me/sei_arb_bot)（约 30 分钟） |
| **策略 2** | 市场周期末尾高机会交易 | [@seitrading_bot](https://t.me/seitrading_bot)（约 1 小时） |
| **策略 3** | 买入 UP/DOWN 之一；流动性变化时，以 $0.01 获取获胜份额 | 即将推出 |

📹 **观看 YouTube 视频**

[![YouTube – Polymarket 5分钟交易机器人](https://img.youtube.com/vi/teeMT-c4S3o/maxresdefault.jpg)](https://www.youtube.com/watch?v=teeMT-c4S3o)

---

## 策略 1：套利（市场中段）

双向买入，合并后收回 USDC。**约 30 分钟体验：** [@sei_arb_bot](https://t.me/sei_arb_bot)
📹 **教程演示：** [YouTube 观看](https://www.youtube.com/watch?v=NsRDKPQrRIs)

### 截图

|  |  |  |
|--|--|--|
| ![image1](assets/image1.png) | ![image2](assets/image2.png) | ![image3](assets/image3.png) |

| 结果 |
|------|
| ![Result](assets/result.png) |

### 功能

- 🔍 自动发现市场 – 自动查找活跃的 BTC 5 分钟市场
- 📊 智能仓位管理 – 监控 UP/DOWN 持仓
- 🛡️ 风险保护 – 市场关闭前自动卖出
- 💰 代币合并 – 从等量持仓中收回 USDC

### 工作原理

1. 查找当前 BTC 5 分钟市场  
2. 监控 UP/DOWN 代币持仓  
3. 合并等量持仓以收回 USDC  
4. 在市场关闭前（30 秒阈值）强制卖出  
5. 自动为下一个市场下单  

---

## 策略 2：周期末尾交易

在市场周期末尾进行高机会交易。**约 1 小时体验：** [@seitrading_bot](https://t.me/seitrading_bot)

### 截图

| 结果 1 |
|--------|
| ![Result 1](assets/result1.png) |

### 功能

- 周期末尾高机会识别
- 自动时机与下单
- 风险可控敞口

### 工作原理

1. 监控当前 5 分钟市场直至结算  
2. 识别周期末尾高机会时刻  
3. 据此下单或调仓  
4. 在市场关闭前管理仓位并平仓  

---

## 策略 3：流动性变化时以 $0.01 获利（即将推出）

**策略：** 通常买入 UP 和 DOWN **其中之一**。当市场流动性变化时，可以以 **$0.01** 获得获胜份额——风险极低，仍为同一加密涨跌市场。

### 截图

| 结果 |
|------|
| ![Result 2](assets/result2.png) |

### 功能

- 超低风险 – 目标每侧 $0.01（UP 和/或 DOWN）
- 利用加密 5 分钟涨跌市场的流动性变化
- 流动性变化时，$0.01 可获获胜份额
- 相同市场结构；不同入场（单侧或双侧最小规模）

### 工作原理

1. 查找当前加密涨跌市场  
2. 监控流动性 – 以约 $0.01 买入 UP 和/或 DOWN（通常为其中一侧）  
3. 流动性变化后，$0.01 建仓可成为获胜份额  
4. 赎回获胜侧或合并两侧持仓；为下一市场重复  

---

## 🚀 快速开始

1. **安装依赖：**
   ```bash
   pip install -r requirements.txt
   ```

2. **配置 `.env`：**
   ```bash
   PRIVATE_KEY=0x...     # 你的钱包私钥
   ORDER_PRICE=0.01      # 限价单价格
   ORDER_SIZE=           # 订单大小
   ```

3. **运行机器人：**
   ```bash
   python main.py
   ```

---

## 📚 文档

- **用户指南：** [docs.md](docs.md) – 如何使用 TG 机器人及入门说明。
