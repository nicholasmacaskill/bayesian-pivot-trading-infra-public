# Strategy 2: Volume Fade / Mean Reversion (Proposed)

## Core Philosophy
Capitalize on overextended moves where price has deviated significantly from value (VWAP) on high volume but failed to continue, signaling exhaustion and a revert to the mean.

## Key Components

### 1. Indicators
- **VWAP (Volume Weighted Average Price):** The "True Value" anchor.
- **RSI (Relative Strength Index):** To detect overbought/oversold conditions (e.g., >70 or <30).
- **Volume Delta:** Buying vs Selling volume pressure.

### 2. Setup Conditions

#### Long Setup (Revert Up)
1. **Extension:** Price dumps significantly BELOW the Lower VWAP Band (2 Standard Deviations).
2. **Exhaustion:** RSI < 30 (Oversold).
3. **Absorption:** High Sell Volume detected, but price creates a long wick or a reversal candle (Hammer/Doji).
4. **Trigger:** Price closes back INSIDE the VWAP band.

#### Short Setup (Revert Down)
1. **Extension:** Price pumps significantly ABOVE the Upper VWAP Band (2 Standard Deviations).
2. **Exhaustion:** RSI > 70 (Overbought).
3. **Absorption:** High Buy Volume detected, but price stalls (Shooting Star/Doji).
4. **Trigger:** Price closes back INSIDE the VWAP band.

### 3. Execution
- **Stop Loss:** Just beyond the recent swing high/low (the exhaustion wick).
- **Take Profit (Target):** The VWAP Baseline (Mean).

## Why this complements SMC Alpha
- **SMC Alpha** is a *Trend Following* and *Breakout* strategy (catching the move start).
- **Volume Fade** is a *Counter-Trend* strategy (catching the move end).
- By running both, the system can profit in trending markets (SMC) and ranging/choppy markets (Mean Reversion) where SMC typically gets stopped out.
