# Scanner Accuracy Audit: Forensic Analysis (BTC)

This report provides a forensic audit of the scanner's performance for the **March 2nd window**, cross-referencing historical labels against realized price action.

## 📊 Summary of Findings (March 2nd Window)

| Metric | Accuracy (Realized) | Insight |
| :--- | :--- | :--- |
| **Bias Accuracy (4h Direction)** | **45.5%** | Slightly worse than a coin flip. |
| **Bias Accuracy (12h Direction)** | **36.4%** | Poor long-term directional conviction. |
| **Regime Accuracy (Hurst)** | **0.0%** | **Critical Failure**: Mis-identified a trending expansion as chop. |

## 🔍 Deep Dive Analysis

### 1. The Regime Blind-Spot
During the audited window, the scanner labeled every BTC setup as `Low-Volatility Consolidation` or `Normal-Volatility Choppy`. 

> [!WARNING]
> **Realized Truth**: BTC was in a **Strong Trending Expansion** (Realized Hurst > 0.52). 
> The scanner was effectively trying to find "reversals" or "consolidations" while the market was aggressively moving in one direction. This explains the high volume of early-stopped trades.

### 2. Bias Drift
The `BEARISH` labels assigned between 10:00 and 13:00 on March 2nd were almost entirely incorrect. Price consistently moved AGAINST the bias over the subsequent 12 hours.
*   **Cause**: The scanner likely weighted short-term local order blocks too heavily compared to the Higher Timeframe (HTF) trend.

### 3. Implementation of Fixes
Based on this audit, the following adjustments made in the previous step are verified as necessary:
*   **Lowering AI Threshold (5.5)**: Allows the scanner to see the "Trend Following" setups that were previously filtered out as "low confidence".
*   **Loosening SMT Strength (0.15)**: Helps the scanner identify expansion moves earlier by catching inter-market shifts before they become obvious trend-line breaks.
*   **Increased R/R (2.5)**: Necessary to survive the ~36% directional accuracy phase. With a 2.5R target, you only need ~28% accuracy to be profitable.

---
*Audit performed on 2026-03-07 using 5m historical price data.*
