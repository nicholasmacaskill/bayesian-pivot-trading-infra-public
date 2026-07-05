# Architectural Case Study: Bayesian Pivot
### Engineering high-Confluence Algorithmic Execution & Cognitive Guardrails

---

## 1. The Intent (Why): The "Orchestration Alpha"

Standard retail trading terminals (TradingView, MT5) and off-the-shelf bots treat execution as a static, isolated trigger: *if price meets parameter X, execute order Y*. In institutional-grade environments, this raw execution model fails due to a lack of **regime awareness** and **cognitive drift**. 

The core strategic challenge solved by **Bayesian Pivot** is the orchestration of execution across three highly fluid variables:
1. **Market Regime (The Physics)**: Markets transition continuously between expansion (momentum), range-bound mean reversion, and random walk (chop). Executing a breakout strategy in a mean-reverting environment, or a range-sweep strategy in a trending expansion, is the primary source of strategy decay.
2. **Account Health (The Constraints)**: Prop firm rules impose strict, dynamic drawdown boundaries. An execution engine must adapt its sizing logic based on real-time proximity to daily loss limits.
3. **The Trader (The Cognitive Tax)**: Discretionary manual execution introduces emotional tilt and latency. When automated, the system misses "Human Alpha"—the subtle, unquantified patterns a seasoned trader perceives.

Standard software cannot run parallel sync buffers, calculate real-time Hurst regime gates, audit human stress biometrics, and close the loop with automated model retraining. **Bayesian Pivot** was built to turn this multi-dimensional loop into a unified, resilient system.

---

## 2. The Structural Density (How): Architectural Resilience

The architecture of **Bayesian Pivot** is structured as an asynchronous, multi-agent pipeline designed around defensive execution.

```
                  [ Multi-Stream Price Data ]
                              │
                    ┌─────────▼─────────┐
                    │ Data Sync Buffer  │ (Coinbase vs yFinance Drift Audit)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  7-Gate Funnel    │ (Time, Level, Sweep, Wick Rejection)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Hurst Exponent   │ (Regime Filter & Trend EMA Alignment)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Risk & Sizing Engine│ (PropGuardian & Psychology Multipliers)
                    └─────────┬─────────┘
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
   [ Structural Alpha ]                 [ High Alpha ]
  (Math-Only Execution)              (Gemini AI Validation)
             │                                 │
             └────────────────┬────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │ Execution Ledger  │ (SQLite DB Records)
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  SFT Retrain Loop │ (Vertex AI JSONL & Few-Shot Prompts)
                    └───────────────────┘
```

### Key Design Decisions:
* **The Synchronized Data Buffer**: To eliminate fake prints and pricing anomalies, the engine runs a parallel stream validator (`fetch_data`). It compares CCXT Coinbase Advanced Trade quotes against Yahoo Finance API streams in real-time. If price delta exceeds `0.5%` or data latency exceeds `120 seconds`, the engine halts to prevent execution during data de-synchronization.
* **The 7-Gate Sovereign Light Funnel**: To capture high-probability sweeps, the system maps 1H swing highs/lows (fractals). A 5m LTF trigger is only validated if it sweeps the HTF level within a specific ATR window (`0.1x to 1.5x ATR`) and closes back inside the level with a wick representing $\ge 30\%$ of the candle range.
* **The Cognitive Circuit Breaker**: The system integrates trader biometrics and direct Telegram polling (`PsychologyEngine` and `BiometricEngine`). If consecutive losses or elevated biometric metrics indicate tilt, the system automatically applies a `0.5x` sizing penalty, scaling down position risk dynamically.

---

## 3. The Recursive Loop (Outcome): The Feedback Moat

By structuring the database around a unified `signed_ledger` (for bot signals) and `journal` (for manual discretionary setups), the system achieves a self-improving feedback loop:

1. **Soft Retraining (Few-Shot Context)**: Every scan cycle, the system extracts the last 10–20 trades (both successes and failures) and feeds them as contextual examples into the live LLM prompt. The validator instantly learns what patterns are failing in the current market environment and adjusts its scoring threshold (e.g. automatically penalizing similar setups).
2. **Hard Retraining (Vertex AI SFT)**: Weekly, the retraining loop outputs instruction-tuned datasets (`training_[timestamp].jsonl`). These files model the exact conditions of successful "Human Alpha" entries, ready for supervised fine-tuning.
3. **Performance Gains**: During optimization runs, SFT integration demonstrated a significant performance lift: average PnL per trade rose from **+$4.21** to **+$57.53** as the model learned to filter out weak setups in choppy environments.

---

## 4. Technical Constraints & Trade-offs

The most critical challenge was the **Latency vs. Conviction** trade-off. 

To run a fully conformed AI audit (DXY intermarket divergence, whale book prints, news feeds, and Gemini LLM validation) required between **1.5 to 3.0 seconds** of API latency. In high-volatility session openings (London/NY Open), a 3-second delay is the difference between a clean limit entry and severe slippage.

### The Solution: Two-Tiered Execution Routing
* **Structural Alpha Routing**: Bypasses the AI Validator entirely. It runs purely on mathematical, local price-action gates (Hurst, ATR, wick ratio). This execution is near-instantaneous (latency under 50ms) and targets 2–3 consistent, smaller-sized setups per day.
* **High Alpha Routing**: Reserved for trend continuation setups. It runs the full AI validation gate, utilizing the Gemini model's reasoning capabilities to evaluate complex confluences. It runs with larger position sizes (`1.0%` risk) but accepts the 3-second latency trade-off because it targets long-duration swing moves where immediate entry tick precision is less critical.
