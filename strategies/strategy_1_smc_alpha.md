# Strategy: SMC Alpha

## Philosophy

The Sovereign Edge Engine operates on Smart Money Concepts (SMC) — a framework for identifying and aligning with institutional order flow rather than trading against it.

The core insight is simple: retail traders are consistently on the wrong side of the market because they react to price rather than anticipate it. Large institutions leave footprints in the market microstructure. This engine reads those footprints.

## High-Level Framework

### 1. Structure First
Before any entry is considered, the system establishes higher-timeframe directional bias. This acts as a filter — only trades aligned with the dominant structure are considered.

### 2. Time-Based Context
Markets don't behave uniformly throughout the day. The system segments the trading session into distinct phases and weights signals accordingly. Not all times are equal.

### 3. Liquidity Awareness
Price is drawn to liquidity. The system models where resting orders are likely clustered (above highs, below lows, at equal highs/lows) and anticipates sweeps before continuation.

### 4. Entry Pattern Hierarchy
Setups are assigned an alpha tier based on structural significance. Higher-alpha patterns require stronger multi-factor confluence before the AI validator will approve them.

### 5. Intermarket Sponsorship
A crypto setup is more reliable when correlated markets (equity futures, dollar index, bond yields) are in agreement. The system quantifies this correlation alignment into a single score called SMT Sponsorship.

### 6. AI Conviction Gate
Every pattern that clears the structural and timing filters is passed to a local LLM for final review. The LLM evaluates the holistic context and assigns a conviction score. Only signals above the configured threshold are acted upon.

---

*Specific parameters, thresholds, pattern detection rules, and scoring weights are proprietary and not published in this repository.*
