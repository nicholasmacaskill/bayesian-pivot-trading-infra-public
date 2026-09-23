# AGENTS.md — Bayesian Pivot Trading Rules & Architectural Constraints

## CRITICAL: Execution & Broker Safety Protocols (TradeLocker / Upcomers)

### 1. Position Bracket Modifications (Stop Loss / Take Profit)
* **RULE:** Modifying Stop Loss (SL) or Take Profit (TP) on an open position **MUST ALWAYS** use the in-place `PATCH` endpoint:
  `PATCH /backend-api/trade/accounts/{account_id}/positions/{position_id}`
  Payload:
  ```json
  {
    "stopLoss": <float>,
    "stopLossType": "absolute",
    "takeProfit": <float>,
    "takeProfitType": "absolute"
  }
  ```
* **STRICT PROHIBITION:** **NEVER** submit a `POST /backend-api/trade/accounts/{account_id}/orders` with `type: "stop"` to update an existing position's stop loss. On TradeLocker, this creates a standalone conditional pending order. In hedging accounts, when the price hits the level, it triggers both orders: closing the initial position and opening a duplicate opposing naked position.

### 2. Position Termination (Closing Positions)
* **RULE:** Closing open positions **MUST ALWAYS** use the dedicated `DELETE` endpoint:
  `DELETE /backend-api/trade/accounts/{account_id}/positions/{position_id}`
* **STRICT PROHIBITION:** **NEVER** attempt to flatten an account by firing opposing market orders via `POST /orders`. This opens hedging positions rather than netting to flat.

### 3. Mandatory Use of Standardized Client Methods (No Raw HTTP Scripts)
* **RULE:** **NEVER** write raw `requests.post()` calls to `/orders` inside scratch scripts or one-off tools.
* All trade operations across all scripts, runners, and manual helpers **MUST** strictly invoke the validated methods in `src/clients/tl_client.py`:
  * `TradeLockerHelper.modify_position_bracket(pos_id, stop_loss, take_profit)`
  * `TradeLockerHelper.close_position(pos_id)`
  * `TradeLockerClient.update_fleet_stop_loss(new_stop_loss, symbol)`
  * `TradeLockerClient.close_all_fleet_positions()`
  * `TradeLockerClient.execute_trade_across_all_accounts(...)`

### 4. Mandatory Post-Execution Reconciliation
* **RULE:** After executing any fleet-wide operation (opening, updating, or closing positions), the agent or runner **MUST** immediately query `GET /positions` and `GET /orders` across all accounts to verify:
  1. Position count matches expected state on 100% of accounts.
  2. Zero stray or orphan pending stop/limit orders remain on any account book.
  3. Every active position has an attached, verified Stop Loss.

### 5. Multi-Account Rate-Limit Pacing & Anti-Desynchronization
* **RULE:** Multi-account fleet operations must enforce **2.0s to 2.5s adaptive pacing** between accounts.
* If any single account fails or receives an HTTP 429, the system must retry or handle the specific failure without leaving partial, unmanaged positions or cross-account direction mismatches.

### 6. Mandatory Protective Brackets on Entry (Zero Naked Trades)
* **RULE:** No order may ever be submitted with `stop_loss=None`. Every trade entry must have a mathematically calculated Stop Loss attached at the exact moment of order placement.

### 7. Upcomers 20% Consistency Rule & Fleet-Wide Payout Target Protocol
* **RULE:** The **20% Consistency Rule** mandates that **no single trading day may account for more than 20.0% of total cumulative net profit** at the time of payout request.
  * Formula: Daily Profit <= 0.20 * Total Target Profit
  * Payout eligibility requires at least 5 distinct profitable trading days; the system targets **15 to 25 consistent sessions** to guarantee spotless prop audit compliance.

* **FLEET TARGET & CONSISTENCY ALLOCATION:**
  * **Hard Payout Threshold Rule:** Payouts are strictly locked until the full balance target is achieved (**$27,000.00** on $25k accounts; **$54,000.00** on $50k accounts). Zero partial or intermediate withdrawals are permitted prior to reaching the full milestone.
  * **$25k Tier (Accounts 1, 3, 7):**
    * Target Net Profit: **+$2,000.00** (Payout Unlock Balance: **$27,000.00**).
    * Max Single-Day Profit: **$400.00** (20% ceiling; system clamped to **$380.00**).
    * Current Status & Decoupled Starting Risk (Live Verified Sep 22, 2026):
      * **Account 1 (`s79qv3xetj`):** Balance **$25,179.07** (+$179.07 buffer above $25,000 locked floor). **Base Risk: $35.00** (**5.1 losses runway** on $179 buffer; scales to $50 at buffer > $600, $70 at buffer > $1,200).
      * **Account 7 (`875do5esrd`):** Balance **$24,139.00** (-$861 DD; +$389.00 buffer above $23,750 floor). **Base Risk: $35.00** (**11.1 losses runway** on $389 buffer).
      * **Account 3 (`q20gxm287x`):** Balance **$24,477.57** (-$522.43 DD; +$727.57 buffer above $23,750 floor). **Base Risk: $50.00** (**14.5 losses runway** on $727 buffer).
  * **$50k Tier (Accounts 2, 6, 9):**
    * Target Net Profit: **+$4,000.00** (Payout Unlock Balance: **$54,000.00**).
    * Max Single-Day Profit: **$800.00** (20% ceiling; system clamped to **$760.00**).
    * Current Status & Decoupled Starting Risk (Live Verified Sep 22, 2026):
      * **Account 9 (`jfcuue7er3` - Oracle Lead Striker):** Balance **$49,803.41** (+$2,303.41 buffer above $47,500 floor). **Base Risk: $100.00** (**23.0 losses runway** on $2,303 buffer; scales to $120 after ~2 wins / cushion >= +$350 above $50k).
      * **Account 2 (`498svcbpfi`):** Balance **$48,500.94** (-$1,499.06 DD; +$1,000.94 buffer above $47,500 floor). **Base Risk: $70.00** (**14.3 losses runway** on $1,000 buffer; scales to $120 at buffer > $1,800).
      * **Account 6 (`dwundrtxjv`):** Balance **$48,622.13** (-$1,377.87 DD; +$1,122.13 buffer above $47,500 floor). **Base Risk: $80.00** (**14.0 losses runway** on $1,122 buffer; scales to $120 at buffer > $1,800).
  * **$10k Tier (Accounts 4, 5, 8):**
    * **Permanently Decommissioned / Liquidation-Only.** Current Balances: Account 4: $9,636.17, Account 5: $9,631.37, Account 8: $9,627.98. Sizing set to **$0.00** (quarantined).

### 8. Strict Communication & Output Formatting Protocols (No LaTeX / Clean English)
* **RULE:** **NEVER** use LaTeX math formatting, dollar sign equation delimiters (`$...$`, `$$...$$`), or raw equation markup (`\ge`, `\le`, `\to`, `\times`, `\text{...}`, `\frac`) in agent responses or documentation.
* **MANDATORY STYLE:**
  - Always write clean, plain English and standard keyboard characters.
  - Write `>=` or "greater than or equal to" (never `$\ge$`).
  - Write `<=` or "less than or equal to" (never `$\le$`).
  - Write `->` or "to" (never `$\to$`).
  - Write `*` or `x` (never `$\times$`).
  - Write `+2.8R`, `-1.0R`, `1.5R` as plain text (never `$+2.8\text{R}$`).
  - Write simple formulas in plain text: `Daily Profit <= 0.20 * Total Profit` or `MFE = (Peak - Entry) / Risk`.
  - Keep all tables, bullet points, numbers, and summaries crisp, plain, and readable.

### 9. Mandatory Adversarial Quality Process & Git Synchronization Protocol
* **RULE:** Any time a change is made to the working live codebase, it **MUST** be run through the full adversarial quality verification process to ensure zero regressions and guarantee the code works correctly in production as intended:
  1. **Automated Invariant & Regression Testing:** Run targeted unit tests and the Master Invariant Harness (`tests/run_bulletproof_harness.py` / `PYTHONPATH=. ./venv/bin/pytest`) to mathematically verify all broker, risk, sizing, and firewall constraints pass.
  2. **Production Integrity Check:** Confirm runtime daemon status, log outputs, and invariant sentry health to ensure production stability.
  3. **Immediate Commit & Remote Push:** Once each change passes the adversarial quality verification, immediately commit with a clean, descriptive message and push the updated code to the private repository (`gitlab main`).

---

### Incident Post-Mortem Reference
* Full forensic documentation: `docs/INCIDENT_2026-08-26_TRADELOCKER_STOP_ORDER_DUPLICATION.md`


