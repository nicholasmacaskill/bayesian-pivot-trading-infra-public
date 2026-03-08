# Strategy Performance Projection: The 2.5 R/R Pivot

This report documents the statistical performance projection for the Bayesian Pivot strategy following the migration to a **1:2.5 minimum Risk-to-Reward ratio** and loosened **AI Threshold (5.5)**.

## Executive Summary
By shifting from a 1.5R target to a **2.5R target**, the strategy's expectancy has moved from significantly negative to **mathematically robust**, even under conservative win rate scenarios.

> [!IMPORTANT]
> **The Sweet Spot**: Maintaining **0.45% risk per trade** provides a 99.7% safety margin against the 6% Max Drawdown limit while projecting a **~46% return** over a 100-trade sequence.

## Monte Carlo Simulation Results (10,000 Iterations)

| Metric | Scenario A (Current Alpha) | Scenario B (Conservative) | Scenario C (Aggressive) |
| :--- | :--- | :--- | :--- |
| **Win Rate** | **52.5%** | **42.0%** | **52.5%** |
| **Risk Per Trade** | 0.45% | 0.45% | **1.00%** |
| **Expected Value** | **+0.377% / trade** | **+0.211% / trade** | **+0.838% / trade** |
| **Median Return (100 trades)** | **+46.37%** | **+23.15%** | **+122.91%** |
| **Avg. Max Drawdown** | 2.63% | 3.78% | 5.76% |
| **95th Percentile DD** | 4.20% | 6.17% | 9.15% |
| **Prob. of 6% DD Breach** | **0.3%** | **6.0%** | **33.0%** |

## Key Insights

### 1. The Power of Skew
At a 42% win rate (Scenario B), the strategy remains profitable with a **99.8% probability of profit** over 100 trades. This proves that the skew (2.5R) is now doing the heavy lifting, protecting the account from the "Fat Tail" risks observed in the previous audit.

### 2. Risk Gating for Prop Firms
Scenario C (1% risk) shows explosive growth (+122%) but carries a **33% risk of breaching the 6% Max Drawdown limit**. 
*   **Recommendation**: Stick to the current `RISK_PER_TRADE = 0.0045` (0.45%) until the account buffer is $>10\%$, then scale slowly to 0.75%.

### 3. Expected Frequency
With the `AI_THRESHOLD` lowered to **5.5**, we expect trade frequency to increase by **~40-60%**, bringing the projected 100-trade sequence into a 2-3 month window.

---
*Simulation generated via `scripts/monte_carlo_projection.py` on 2026-03-07.*
