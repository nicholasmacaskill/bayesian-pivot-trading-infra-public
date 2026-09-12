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
  * Formula: $\text{Daily Profit} \le 0.20 \times \text{Total Target Profit}$
  * Payout eligibility requires at least 5 distinct profitable trading days; the system targets **15 to 25 consistent sessions** to guarantee spotless prop audit compliance.

* **FLEET TARGET & CONSISTENCY ALLOCATION:**
  * **Hard Payout Threshold Rule:** Payouts are strictly locked until the full balance target is achieved (**$27,000.00** on $25k accounts; **$54,000.00** on $50k accounts). Zero partial or intermediate withdrawals are permitted prior to reaching the full milestone.
  * **$25k Tier (Accounts 1, 3, 7):**
    * Target Net Profit: **+$2,000.00** (Payout Unlock Balance: **$27,000.00**).
    * Max Single-Day Profit: **$400.00** (20% ceiling; system clamped to **$380.00**).
    * Base Risk: **$40.00** (scales to $60 at buffer > $600, $80 at buffer > $1,200; 7+ loss runway on Account 1's $286 buffer).
    * Current Status:
      * **Account 1 (`s79qv3xetj`):** Balance ~$25,286 (+$286 in profit; Floor locked at $25,000). Needs **+$1,714** $\rightarrow$ **~4 to 5 weeks** at $40 risk.
      * **Account 3 (`q20gxm287x`):** Balance ~$24,697 (-$303 DD; Floor $23,750). Needs **+$2,303** $\rightarrow$ **~5 to 6 weeks** at $40 risk.
      * **Account 7 (`875do5esrd`):** Balance ~$24,344 (-$656 DD; Floor $23,750). Needs **+$2,656** $\rightarrow$ **~6 to 7 weeks** at $40 risk.
  * **$50k Tier (Accounts 2, 6):**
    * Target Net Profit: **+$4,000.00** (Payout Unlock Balance: **$54,000.00**).
    * Max Single-Day Profit: **$800.00** (20% ceiling; system clamped to **$760.00**).
    * Base Risk: **$80.00** (scales to $120 at buffer > $1,500, $160 at buffer > $2,500; 13-16+ loss runway).
    * Current Status:
      * **Account 6 (`dwundrtxjv`):** Balance ~$48,801 (-$1,199 DD; Floor $47,500). Needs **+$5,199** $\rightarrow$ **~5 to 7 weeks** at $80 risk.
      * **Account 2 (`498svcbpfi`):** Balance ~$48,567 (-$1,433 DD; Floor $47,500). Needs **+$5,433** $\rightarrow$ **~6 to 8 weeks** at $80 risk.
  * **$10k Tier (Accounts 4, 5, 8):**
    * **Permanently Decommissioned / Liquidation-Only.** Sizing set to **$0.00** (quarantined).

---

### Incident Post-Mortem Reference
* Full forensic documentation: `docs/INCIDENT_2026-08-26_TRADELOCKER_STOP_ORDER_DUPLICATION.md`
