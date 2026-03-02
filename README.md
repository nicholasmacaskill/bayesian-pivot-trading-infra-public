# Sovereign SMC: Institutional Intelligence Suite 🧠💎

**The Apex of ICT Automation & AI-Augmented Trading.**

Sovereign SMC is a bespoke institutional trading framework that synthesizes Inner Circle Trader (ICT) concepts with high-frequency execution, **Vertex AI fine-tuned validation**, and a multi-tier **Institutional Filtration Engine**.

---

##  The Sovereign Filtration Stack (Tiered Audit)
Every trade signal must survive a 4-tier "Gauntlet" before execution. If a setup fails even one sub-filter, it is discarded to protect capital.

### Tier 1: The Hard Gates (Contextual Logic)
- **Time (Killzone Filter)**: Restricts trading to high-probability institutional windows:
  - **Asian Session Fade**: 11 PM – 2 AM EST (4–7 AM UTC) — *Prime Alpha Window*
  - **London Open**: 2 AM – 5 AM EST (7–10 AM UTC) — *Inducement Phase*
  - **NY Continuous**: 7 AM – 3 PM EST (12–20 PM UTC) — *Full Session*
- **Macro News Pulse**: The `NewsFilter` spiders CryptoPanic and high-impact calendars. All trading is halted 30m before/after "Red Folder" events.
- **Equity Guard**: A hard stop on the engine if the **Max Daily Loss (2 trades)** or **Equity Drawdown (6%)** is reached.

### Tier 2: Quantitative Regime Detection
- **Hurst Exponent (Regime ID)**: The engine calculates the Hurst Exponent (`H`) to determine the market "State":
  - `H < 0.5`: **Mean Reversion**. Activates "Turtle Soup" and "Range Fade" strategies.
  - `H > 0.5`: **Persistence/Momentum**. Activates "FVG Taps" and "BOS Continuation" entries.
- **ADF (Augmented Dickey-Fuller)**: Performs stationarity tests to ensure the market isn't in a "Random Walk" (Brownian Motion) where edges are neutralized.
- **ATR Displacement Filter**: Market Structure Shifts (MSS) are only validated if the price break is confirmed by an **ATR-weighted displacement candle** (High Volatility Floor).

### Tier 3: Structural Institutional Confluence (ICT Edge)
- **Double Quartile Gate**: Price is decimated into quadrants based on the **Asian Range** and **CBDR**:
  - **Longs**: Only valid in **Deep Discount** (Bottom 25-50% of the range).
  - **Shorts**: Only valid in **High Premium** (Top 25-50% of the range).
- **Intersymbol Sponsorship (SMT Divergence)**: No trade is taken in isolation.
  - **BTC vs. ETH**: Requiring divergence at key liquidity pools.
  - **DXY Integration**: Cross-asset confirmation from the US Dollar Index.
- **Level 2 Liquidity Filter**: The `validate_sweep_depth` logic spiders the exchange Order Book. A liquidity sweep is only considered "Smart Money" if the engine detects significant **Order Absorption** (>5.0 BTC volume depth).

### Tier 4: The AI Gatekeeper (Gemini 2.0 SFT)
The final decision is made by a **Supervised Fine-Tuned (SFT)** model on Vertex AI. This turns a standard "Math-Based" scanner into an Institutional Intelligence model.
- **Footprint Recognition**: The model is trained on a proprietary dataset of **Human Alpha** (discretionary winning trades) to identify "Inducement" (Retail Traps) versus "Institutional Displacement."
- **Institutional Confidence Score**: Ranks setups from 0-10. 
  - `AI_THRESHOLD`: 8.0/10 for standard setups.
  - `AI_THRESHOLD_ASIAN_FADE**: 7.5/10 (higher historical win rate window).
- **Alpha Digitization**: This layer captures the "Instinct" that standard math-based indicators miss.

---

## 🛡️ The Mathematical Moat: Alpha vs. Math
The Sovereign framework is designed such that the **Raw Scanner Math** (Tier 1-3) identifies *possible* setups, while the **AI Gatekeeper** (Tier 4) identifies *profitable* ones.
- **Raw Math Win-Rate**: ~19.9% (Market Liquidity Traps)
- **AI-Integrated Win-Rate**: Targeted Institutional Alpha (>75% expected).

*Note: The public code provides the 'Engine' (The Math), but the 'Sovereign Intelligence' (The Fine-Tuned Weights) is hosted in an encrypted enclave and refreshed weekly via Human-in-the-Loop training.*

---

## 🎯 Institutional Draw on Liquidity (TP Targeting)
Targets are dynamically calculated based on the "Path of Least Resistance":
1.  **Unfilled FVGs**: The engine scans for the nearest price imbalance acting as a magnet.
2.  **Swing High/Low Liquidity**: Targeting the resting stop-losses of retail participants.
3.  **Volatility-Adjusted SD**: Using Standard Deviation expansions (+1/+2 SD) of the session range for TP2/TP3.

---

## 🚀 Sniper Operations: Yard Mode
- **Sub-Second Latency**: Local sniper runner avoids cloud hops for precision entries.
- **Yard Mode persistence**: macOS `caffeinate` ensures the Mac stays awake while the engine scans at 60-second institutional polling intervals.
- **Execution Audit**: The `ExecutionAuditEngine` reconciles all signals with real TradeLocker executions for full accountability.

---

## 🔒 Security
- **Confidential Release**: Geometric Alpha constants and proprietary CSV training datasets are redacted in this public export.
- **Zero-Trust Keys**: All credentials stored in `.env.local` (Never committed to Git).
- **The "Leaked" Trap**: Trading the raw math signals without the AI Gatekeeper is a negative expectancy system.

*Sovereign SMC: Built for the 1% who trade with the 0.1%.*
