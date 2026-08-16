# 📈 TradingView Paper Trading Strategies — Sovereign SMC

This directory contains **3 Pine Script v5 Strategy Scripts** designed for TradingView backtesting and paper trading. Each script mirrors one of the quantitative strategy profiles operating in our Python infrastructure.

---

## 🎯 The 3 Strategy Profiles

### 1. **Trend Expansion Operator** ([`strategy_1_trend_expansion.pine`](file:///Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra/strategies/tradingview/strategy_1_trend_expansion.pine))
- **Target Timeframes**: `5m`, `15m`, `1h`
- **Strategy Focus**: Persistent trend momentum, EMA alignment (20/50), Market Structure Shift (MSS), and Fair Value Gap (FVG) entries.
- **Risk Profile**: `3.0R` Target with `2.0 ATR` Stop Loss.
- **Matched Account Mandate**: `Account B` ($49.3k Volume Expansion).

### 2. **Turtle Soup Reversal Fader** ([`strategy_2_turtle_soup_fader.pine`](file:///Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra/strategies/tradingview/strategy_2_turtle_soup_fader.pine))
- **Target Timeframes**: `5m`, `15m`
- **Strategy Focus**: Liquidity sweeps above/below 20-bar session highs/lows. Fades retail inducement sweeps with tight stop loss.
- **Risk Profile**: `2.5R` Target with `1.5 ATR` Stop Loss.
- **Matched Account Mandate**: `Account C` ($25.0k Turtle Soup Fader).

### 3. **High Alpha Aggressive Scalper** ([`strategy_3_high_alpha_scalper.pine`](file:///Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra/strategies/tradingview/strategy_3_high_alpha_scalper.pine))
- **Target Timeframes**: `1m`, `5m`
- **Strategy Focus**: High volume spikes ($>1.8\times$ 20-bar SMA), Micro-FVG expansion, and dynamic break-even trailing stop at $+1.0R$.
- **Risk Profile**: `2.0R` Quick Scalp Target with `1.2 ATR` Stop Loss.
- **Matched Account Mandate**: `Account E` ($10.0k Aggressive Scalper).

---

## 🚀 How to Load and Run in TradingView

1. Open **[TradingView](https://www.tradingview.com)** and navigate to your target symbol (e.g. `BTCUSD` or `ETHUSD`).
2. Open the **Pine Editor** tab at the bottom of the screen.
3. Open one of the `.pine` files above:
   - [`strategy_1_trend_expansion.pine`](file:///Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra/strategies/tradingview/strategy_1_trend_expansion.pine)
   - [`strategy_2_turtle_soup_fader.pine`](file:///Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra/strategies/tradingview/strategy_2_turtle_soup_fader.pine)
   - [`strategy_3_high_alpha_scalper.pine`](file:///Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra/strategies/tradingview/strategy_3_high_alpha_scalper.pine)
4. Copy and paste the entire code into the Pine Editor and click **Save** $\rightarrow$ **Add to chart**.
5. Switch to the **Strategy Tester** tab to inspect automated paper trading performance, win rate, total drawdown, and profit factor.
6. Connect TradingView Paper Trading to enable live simulated orders on the chart.
