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

---

### Incident Post-Mortem Reference
* Full forensic documentation: `docs/INCIDENT_2026-08-26_TRADELOCKER_STOP_ORDER_DUPLICATION.md`
