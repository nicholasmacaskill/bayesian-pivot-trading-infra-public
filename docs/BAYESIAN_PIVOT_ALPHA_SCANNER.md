# Bayesian Pivot Alpha Scanner: Dynamic Turtle Soup Strategy

The Bayesian Pivot Alpha Scanner is a premium, high-conviction signal generator designed to produce exactly 2–3 institutional-grade setups per day. It strips away complex indicators to focus entirely on the core edge verified by historical trade audits: **Liquidity sweeps of high-timeframe (HTF) support and resistance levels followed by lower-timeframe (LTF) candle rejection (the Turtle Soup pattern).**

---

## Strategy Logic

### 1. High-Timeframe Level Mapping
The scanner maps major key levels using fractal structures (swing highs and lows) on the **1H timeframe**:
- **HTF Swing Highs (Resistance)**: Key liquidity pools where short stops/buy stops are clustered.
- **HTF Swing Lows (Support)**: Key liquidity pools where long stops/sell stops are clustered.

### 2. Time-Gating: Killzone Constraints
To avoid market noise, low volume, and random chop, the scanner only searches for setups during prime session windows (Killzones):
- **London Open Killzone**: `07:00 – 10:00 UTC`
- **New York Open Killzone**: `12:00 – 15:00 UTC` (New York Open and initial execution run)
- **Asian Fade Window**: `04:00 – 07:00 UTC` (Fading the Asian range high/low)

*Note: Setups detected outside these windows are strictly discarded.*

### 3. Hurst Exponent Dynamic Regime Gate
To adapt automatically to trending vs. mean-reverting environments, the scanner calculates the Hurst Exponent ($H$) on the 1H timeframe:
- **Trending Regime ($H > 0.55$)**: Enforce trend alignment.
  - Buy sweeps only if the overall market is in a structural uptrend.
  - Sell sweeps only if the overall market is in a structural downtrend.
- **Mean-Reverting/Chop Regime ($H < 0.45$)**: Disable trend alignment.
  - Market is range-bound; scan for and execute sweeps at both boundaries.
- **Random Walk / Transition ($0.45 \le H \le 0.55$)**: Neutral. Enforce a defensive/moderate gate or align with local structure.

### 4. Liquidity Sweep & Wick Rejection Rules (Turtle Soup)
The scanner identifies the setup when price pierces a mapped level and immediately rejects:
- **Long Setup (Sell Stop Liquidity Sweep)**:
  - Price sweeps *below* a 1H swing low.
  - Sweep depth is validated against ATR to ensure a significant sweep (e.g., between $0.2 \times \text{ATR}$ and $1.5 \times \text{ATR}$ below the level).
  - The LTF (5m) candle closes *above* the swept level, leaving a clear lower wick (rejection).
- **Short Setup (Buy Stop Liquidity Sweep)**:
  - Price sweeps *above* a 1H swing high.
  - Sweep depth is validated against ATR.
  - The LTF (5m) candle closes *below* the swept level, leaving a clear upper wick (rejection).

---

## Mathematical Symmetry
To prevent directional bias and overfitting, identical parameters and mathematical rules apply to both Longs and Shorts:
- Standardized ATR multipliers for sweep distance.
- Standardized minimum wick ratio (e.g., wick must represent at least 30% of the candle's total range).
- Identical Hurst exponent gates for both directions.
