# Strategy 1: SMC Alpha (Current)

## Core Philosophy
Allows the algorithm to act as a "Liquidity Hunter," identifying and trading institutional order flow by spotting where retail traders are trapped (liquidity sweeps) and where smart money is entering (displacement).

## Key Components

### 1. Market Structure & Bias (4H Timeframe)
- **Trend Determination:** Uses 20 EMA vs 50 EMA on the 4H chart.
  - 20 > 50 = BULLISH Bias (Look for Longs)
  - 20 < 50 = BEARISH Bias (Look for Shorts)

### 2. Time Operations (Killzones)
- **Session:** New York Continuous (12:00 - 20:00 UTC).
- **Session Quartiles:** Breaks the session into 90-minute "Quartiles" to identify the phase:
  - Q1: Accumulation
  - Q2: Manipulation (The "Judas Swing")
  - Q3: Distribution
  - Q4: Continuation/Reversal

### 3. Price Operations (Liquidity Pools)
Calculates key levels based on prior price action:
- **Asian Range (00:00 - 05:00 UTC):** Defines the baseline range.
- **London Range:** Used as an inducement target.
- **Deep Discount/Premium:** Only looks for Longs in the lower 50-60% of the daily range, and Shorts in the upper 50-60%.

### 4. Entry Patterns
#### A. The Judas Sweep (High Alpha)
- **Long:** Price sweeps BELOW a recent low (Previous Daily Low or London Low) but closes ABOVE it.
- **Short:** Price sweeps ABOVE a recent high (Previous Daily High or London High) but closes BELOW it.
- **Confirmation:** Requires Level 2 Order Book verification (Whale Absorption of >5 BTC).

#### B. Trend Pullback (Medium Alpha)
- **Long:** Price taps into a Bullish Fair Value Gap (FVG) while in a Bullish Trend.
- **Short:** Price taps into a Bearish FVG while in a Bearish Trend.

### 5. Risk Management
- **Risk Per Trade:** 0.65% of Equity.
- **Stop Loss:** Dynamic based on ATR (Volatility).
- **Targets:**
  - TP1: 1.5R (Bank profit)
  - TP2: 3.0R (Runner)

### 6. Trinity of Sponsorship (Intermarket)
Validates setups against DXY, 10Y Yields, and NQ/ES futures.

- **Indices (NQ/ES):** Risk-on correlation. Rising NQ supports Bullish BTC.
- **DXY (Dollar):** Inverse correlation. Falling DXY supports Bullish BTC.
- **TNX (10Y Yield):** Inverse correlation. Falling Yields support Bullish BTC (Risk-on).

**SMT Divergence:**
The algorithm specifically looks for "Cracks in Correlation":
- If NQ makes a Lower Low but BTC makes a Higher Low -> **Bullish SMT** (Accumulation).
- If DXY makes a Higher High but BTC makes a Higher High -> **Bearish SMT** (Weakness).

### 7. Event & Volatility Context (Gates)
- **News Soft-Gate:**
  - Checks economic calendar.
  - If High Impact Event is imminent, logs "ACTIVE EVENT" and proceeds with CAUTION (manual review advised).
  - DOES NOT block the trade automatically but flags context.

- **ATR-Dynamic Targeting:**
  - Adjusts profit targets based on volatility regime.
  - **High Volatility (ATR > 1.5x Mean):** Targets 2.0 SD (Expansion).
  - **Low Volatility (ATR < Mean):** Targets 50% Mean Reversion (Tight).
  - **Normal:** Targets 1.0 SD.
