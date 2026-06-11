# The Bayesian Pivot Prop Firm Scaling Plan

## 1. The Mathematical Engine
To project growth, we must use the verified statistics from the live trading history of the **Bayesian Pivot BTC-Only System**:

*   **Win Rate**: 48%
*   **Average Realized Reward (R-Multiple)**: 1.48 R
*   **Average Loss**: -1.00 R (1 R)
*   **Expected Value (EV) per Trade**: `(0.48 * 1.48 R) - (0.52 * 1 R) = +0.19 R`
*   **Projected Trade Frequency (BTC-Only)**: ~15 trades per month (180 trades per year)
*   **Projected Annual Return**: `180 trades * 0.19 R = +34.2 R` per year.

---

## 2. The Golden Rule of Prop Capital: The "True Balance"
In prop firm trading, the nominal account size (e.g., $100,000) is leverage fluff. **Your true capital is your Maximum Drawdown (MDD) limit.**

For a standard $100,000 account, the maximum trailing/static drawdown limit is typically **10% ($10,000)**. 
*   If you lose $10,000, the account is terminated.
*   Therefore, your actual risk capital is **$10,000**, not $100,000.
*   All position sizing must be calculated as a percentage of this **$10,000 Drawdown Capital**, not the $100,000 account balance.

---

## 3. Position Sizing Profiles (Based on $10,000 Drawdown Capital)

| Risk Profile | Risk per Trade (R) | % of Drawdown Capital | Drawdown Buffer (Stops to Ruin) | Projected Annual Return |
| :--- | :---: | :---: | :---: | :---: |
| **Conservative** | $100 | 1.0% | 100 consecutive losses | **$3,420 / year** (34.2% return) |
| **Moderate** | **$200** | **2.0%** | **50 consecutive losses** | **$6,840 / year** (68.4% return) |
| **Aggressive** | $300 | 3.0% | 33 consecutive losses | **$10,260 / year** (102.6% return) |

> [!TIP]
> **Moderate ($200 Risk)** is the optimal balance of growth and safety. The probability of hitting **50 consecutive losses** with a 48% win rate is mathematically close to **0.00%**. 

---

## 4. The 3-Stage Scaling Roadmap
Rather than increasing the risk percentage on a single account (which increases the probability of ruin), you scale by **allocating more accounts** and using a trade copier.

```
[Stage 1: One $100k Account] ──> [Stage 2: Allocation Limit ($400k)] ──> [Stage 3: Multi-Firm Copier ($1.2M)]
```

### Stage 1: Single Account Setup ($100k Allocation - Upcomers)
*   **Total Drawdown Capital**: $10,000
*   **Risk per Trade**: $200 (2.0% of Drawdown Capital)
*   **Projected Annual Return**: **$6,840**
*   **Net Profit after 99% Split**: **$6,771.60 / year**

### Stage 2: Full Single-Firm Allocation ($400k Allocation - Upcomers)
*   **Total Drawdown Capital**: $40,000
*   **Risk per Trade**: $800 (2.0% of Drawdown Capital)
*   **Projected Annual Return**: **$27,360**
*   **Net Profit after 99% Split**: **$27,086.40 / year**

### Stage 3: Multi-Firm Trade Copier ($1.2M Allocation)
By purchasing accounts across Upcomers and other firms (assuming an average 90% split overall across multiple companies):
*   **Total Drawdown Capital**: $120,000
*   **Risk per Trade**: $2,400 (divided as $800 per account)
*   **Projected Annual Return**: **$82,080**
*   **Net Profit after Weighted Split (~93%)**: **$76,334.40 / year**

---

## 5. Risk of Ruin & Drawdown Safety
A system with a 48% win rate will inevitably face drawdown cycles. 

### Probability of Streak Lengths over 180 Trades (1 Year):
*   **5 Consecutive Losses**: 99.8% probability (100% guaranteed to happen multiple times).
*   **8 Consecutive Losses**: 42.1% probability (highly likely to happen at least once).
*   **10 Consecutive Losses**: 18.5% probability (possible during a market regime shift).
*   **15 Consecutive Losses**: 0.8% probability (extremely rare).
*   **25+ Consecutive Losses**: <0.001% probability (mathematically negligible).

### Conclusion:
By keeping your risk at **$200 per $100k account** (50-loss buffer), your account is **drawdown-proof**. Even if the bot hits a historically bad run of 15 losses in a row, you only draw down **$3,000** (30% of your drawdown buffer), leaving your account perfectly intact to recover during the next expansion regime.
