# Bayesian Pivot Alpha Scanner: Strategy Specifications, Outputs & Case Studies

This document provides a clear breakdown of the active trading strategies in the codebase, the exact line-by-line output format of their alerts, and historical case studies from your profitable trade logs demonstrating these setups in action.

---

## 1. Strategy Categorization & Specifications

The system operates three primary strategy modules. The new Bayesian Pivot Turtle Soup scanner runs purely on mathematical rules and bypasses the LLM to avoid latency and credit usage, while the legacy FVG and OB scanners run through the Gemini AI validation gate.

### Strategy A: Bayesian Pivot Turtle Soup (Math-Only, 9.0/10 Conviction)
* **Logic**: Mapped 1H swing highs/lows are swept by a 5m candle, which immediately rejects and closes back inside the level.
* **Hurst Regime Filter**:
  - **Trending ($H > 0.55$)**: Enforces 1H trend alignment using a 50 EMA. Longs allowed only in uptrends; Shorts allowed only in downtrends.
  - **Mean-Reverting ($H < 0.45$)**: Trend alignment disabled. Scans and executes sweeps at both support and resistance.
  - **Chop ($0.45 \le H \le 0.55$)**: All setups are blocked.
* **Wick Rejection Filter**: The rejection wick must be $\ge 30\%$ of the 5m candle's total range.
* **ATR relative Sweep Depth**: Sweep must pierce the 1H level by between $0.1 \times \text{ATR}(14)$ and $1.5 \times \text{ATR}(14)$ of the 5m timeframe.
* **Risk & Sizing**: Uses `Config.FIXED_RISK_USD` ($100.0), reduced by 50% ($50.0) for Longs to account for historical long drawdown trends. Take profit is set at a static $3.0 \times$ risk, clamped if potential profit exceeds $400.0.

### Strategy B: FVG Retest (AI-Validated, Variable Score)
* **Logic**: Price creates a 5m Fair Value Gap (displaced expansion) and subsequently retraces to tap the FVG boundary.
* **AI Validation**: A Gemini model scores the setup based on multi-timeframe structure, DXY convergence, and news. Setup executes only if AI Score $\ge 8.0$.
* **Risk & Sizing**: Position sizing is scaled according to trust tiers:
  - **Aggressive Tier (Score 90+)**: 1.0% risk.
  - **Conservative Tier (Score 75-89)**: 0.5% risk.
  - **Below 75**: Setup rejected.

### Strategy C: Order Block Rebound (AI-Validated, Variable Score)
* **Logic**: Price undergoes a Market Structure Shift (MSS) leaving a structural Order Block (last down-candle before up-move, or last up-candle before down-move) at the origin, followed by a mitigation retest.
* **AI Validation**: Requires Gemini model review confirming structural validity and scoring $\ge 8.0$.
* **Risk & Sizing**: Scaled according to the same 75/90 AI trust tiers.

---

## 2. Output Format Templates

Below are the exact line-by-line formats generated in Telegram for each strategy.

### Output 1: Bayesian Pivot Turtle Soup (LONG Setup Example)
```
🟢 🦄 UNICORN: BTC/USD
🛡️ [SECURE] | 🏁 LONDON_OPEN — EXECUTION | 📉 Buffer: $7,500

🦅 THE HUNT
• Active Strategy: Bayesian Pivot Turtle Soup LONG (MEAN_REVERSION) (9.0/10)
• Hunt Logic: Turtle Soup Liquidity Sweep of HTF level 64620.00. Hurst: 0.380 (MEAN_REVERSION). Wick Rejection confirmed on 5m candle.

📐 BIAS CONFLUENCE
• Daily: SIDEWAYS | HTF: RANGE-BOUND | Intermarket: N/A

🎯 LIQUIDITY EDGE
• Draw on Liquidity: 64,620.0000 (SWING_LOW)
• Gravity: 120.0 pips

🔬 SYSTEM STATE
• Mood: Focused (Biometric Secure) | Alpha Persistence: 1.00x
• Volatility: 42th %ile | Slip: 0.01% (Optimal)

💷 EXECUTION
• Entry: $64,500.0000 | SL: $64,250.0000 | TP: $66,375.0000
• Position Size: 0.4 | Position Value: $25,800.00

⚠️ HISTORICAL RISK ALERT: Long trades represent your largest manual draw. Ensure strict limit execution and 50% risk reduction ($50 USD max risk).

📊 View on TradingView
```

### Output 2: FVG Retest (AI-Validated Setup Example)
```
🟢 🦅 HIGH ALPHA: BTC/USD
🛡️ [SECURE] | 🏁 NY_CONTINUOUS — AM_SESSION | 📉 Buffer: $6,120

🦅 THE HUNT
• Active Strategy: Bullish FVG Retest (8.5/10)
• Hunt Logic: Entry triggers on LTF 5m bullish FVG tap following DXY liquidity sweep. AI confirmation index high.

📐 BIAS CONFLUENCE
• Daily: BULLISH | HTF: BULLISH | Intermarket: BEARISH_SWEEP

🎯 LIQUIDITY EDGE
• Draw on Liquidity: 68,150.0000 (EQH)
• Gravity: 73.0 pips

🔬 SYSTEM STATE
• Mood: Focused | Alpha Persistence: 1.00x
• Volatility: 65th %ile | Slip: 0.02% (Optimal)

💷 EXECUTION
• Entry: $67,420.0000 | SL: $67,220.0000 | TP: $67,920.0000
• Position Size: 0.7 | Position Value: $47,194.00

⚠️ HISTORICAL RISK ALERT: Long trades represent your largest manual draw. Ensure strict limit execution and 50% risk reduction ($50 USD max risk).

📊 View on TradingView
```

### Output 3: Order Block Rebound (AI-Validated Setup Example)
```
🟢 🦄 UNICORN: BTC/USD
🛡️ [SECURE] | 🏁 LONDON_OPEN — EXECUTION | 📉 Buffer: $8,000

🦅 THE HUNT
• Active Strategy: Bullish OB Rebound (9.2/10)
• Hunt Logic: Structural validation of 1H demand block at origin of recent MSS. Mitigated on 5m return.

📐 BIAS CONFLUENCE
• Daily: BULLISH | HTF: CONSOLIDATION | Intermarket: BULLISH_EXPANSION

🎯 LIQUIDITY EDGE
• Draw on Liquidity: 65,800.0000 (SWING_HIGH)
• Gravity: 180.0 pips

🔬 SYSTEM STATE
• Mood: Analytical | Alpha Persistence: 1.20x
• Volatility: 50th %ile | Slip: 0.01% (Optimal)

💷 EXECUTION
• Entry: $64,800.0000 | SL: $64,550.0000 | TP: $65,550.0000
• Position Size: 0.6 | Position Value: $38,880.00

⚠️ HISTORICAL RISK ALERT: Long trades represent your largest manual draw. Ensure strict limit execution and 50% risk reduction ($50 USD max risk).

📊 View on TradingView
```

---

## 3. Case Studies: Profitable Logs Ground Truth

These examples from your historical trade audit logs show the precise edge that our mathematical filters are designed to capture:

### Case Study 1: Classic Support Sweep & Reversal (Trade ID: `7349874591885776214`)
* **PnL**: `+$936.30`
* **Entry Price**: `$67,404.90`
* **Setup Logic**: Classic Turtle Soup support sweep. Price swept clean below the previous 1H swing low/support level to trap sell stop liquidity before printing a swift wick rejection and reversing into a bullish structural shift.
* **Audit Verdict**: Structural Alpha. Discretionary entry captured high-conviction institutional absorption of retail stop-losses.

### Case Study 2: Low-Timeframe Demand Sweep (Trade ID: `7349874591886176853`)
* **PnL**: `+$896.93`
* **Entry Price**: `$73,683.60`
* **Setup Logic**: Liquidity sweep of minor swing lows within an established range, followed by a swift Market Structure Shift (MSS) to the upside. The execution occurred precisely on the rejection retest of the swept boundary.
* **Audit Verdict**: High-Conviction Structural Trade. Capitalized on clean stop-loss run.

### Case Study 3: Resistance Sweep & Fade (Trade ID: `7349874591886174316`)
* **PnL**: `+$748.98`
* **Entry Price**: `$73,654.00`
* **Setup Logic**: Sweep of resistance high. Trapped early buyers before reverting into a range expansion. Rejection on the 5m candle closed back inside the 1H swing high zone, triggering the entry.
* **Audit Verdict**: Valid structural edge capturing the fade window.
