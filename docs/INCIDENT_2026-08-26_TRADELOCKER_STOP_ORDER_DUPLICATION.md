# INCIDENT POST-MORTEM REPORT: TradeLocker Stop-Order Duplication Bug

**Incident Date:** 2026-08-26  
**Status:** RESOLVED & CODE HARDENED  
**Severity:** Critical (Execution / Financial Loss)  
**Total Fleet Financial Impact:** -$481.76 USD across 8 funded demo accounts (~$60.22/account)

---

## 1. Executive Summary
On August 26, 2026, while managing an active BTC/USD Long position across the 8-account TradeLocker fleet, an update script intended to modify the Stop Loss to `$78,180.00` mistakenly submitted a `POST /backend-api/trade/accounts/{acc}/orders` with `type: "stop"`. 

On TradeLocker (specifically brokers operating in hedging mode like Upcomers), `POST /orders` does **not** modify an existing position bracket. Instead, it creates an independent, standalone pending stop order on the broker's book without cancelling the original stop loss.

When BTC dropped to `$78,180.00` at 12:30:20 UTC:
1. **Stop Order #1** executed: Sold 0.12 BTC and closed the Long position.
2. **Stop Order #2** executed immediately afterward: Sold *another* 0.12 BTC on the newly flat account, opening an **accidental 0.12 BTC Short (Sell) position** without Stop Loss or Take Profit brackets.

Subsequent attempts to flatten rate-limited on 5 accounts, leaving 5 naked short positions open while BTC rebounded to `$78,780.00`.

---

## 2. Forensic Timeline

| Time (UTC) | Event / Action | Broker State |
| :--- | :--- | :--- |
| **09:53:34** | Original BTC/USD Long entry placed across fleet (`0.12 BTC`). | Long position opened (`...010594`). Stop Order #1 created on broker book (`...510613`). |
| **12:16:25** | Helper script ran to widen Stop Loss to `$78,180.00`. | **BUG:** Sent `POST /orders` with `type: "stop"`. Created duplicate Stop Order #2 (`...538882`) on broker book. |
| **12:30:21** | Market price swept down to `$78,180.00`. | **Stop Order #1 triggered:** Closed the Long.<br>**Stop Order #2 triggered:** Opened an accidental **0.12 BTC Short position** (`...014441`) with no SL/TP. |
| **12:35:45** | Flatten script attempted to close the accidental shorts. | Accounts 1–3 closed with realized losses (-$158.23 total). Accounts 4–8 rate-limited (HTTP 429/timeout), leaving 5 open shorts. |
| **16:05:00** | User inspected TradeLocker UI. | Discovered 5 open Short positions with unattached SL/TP and inverted Take Profit display. |

---

## 3. Root Cause Analysis (RCA)

### Why Did This Happen?
1. **Broker API Paradigm Mismatch:** 
   * In standard MetaTrader environments, setting a stop loss updates the ticket.
   * On TradeLocker, position brackets **must** be updated via:
     ```http
     PATCH /backend-api/trade/accounts/{account_id}/positions/{position_id}
     Content-Type: application/json

     {
       "stopLoss": 78180.0,
       "stopLossType": "absolute",
       "takeProfit": 79150.0,
       "takeProfitType": "absolute"
     }
     ```
   * Calling `POST /orders` with `type: "stop"` submits an **independent conditional pending order**.
2. **Hedging Mode Order Independence:**
   * Upcomers allows simultaneous long and short positions. Opposing orders do not net out unless explicitly linked to a position ID or closed via the position termination endpoint.
3. **Missing Validation Guard:**
   * There was no assertion in the execution client preventing raw `POST /orders` from being invoked when updating position brackets.

---

## 4. Financial Impact Audit

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              FINANCIAL AUDIT BREAKDOWN                                 │
├─────────┬──────────────────────────┬──────────────────┬──────────────┬─────────────────┤
│ Account │ Account Email            │ Position ID      │ Status       │ Financial Impact│
├─────────┼──────────────────────────┼──────────────────┼──────────────┼─────────────────┤
│ Acc 1   │ s79qv3xetj@upcomers.com  │ -                │ Closed       │ -$87.82         │
│ Acc 2   │ 498svcbpfi@upcomers.com  │ -                │ Closed       │ -$39.54         │
│ Acc 3   │ q20gxm287x@upcomers.com  │ -                │ Closed       │ -$30.87         │
│ Acc 4   │ vkrbpwdprh@upcomers.com  │ 288230376155014441│ Manual SL/TP │ -$67.84 (flt)   │
│ Acc 5   │ hnr10rtj4k@upcomers.com  │ 288230376155014437│ Manual SL/TP │ -$64.82 (flt)   │
│ Acc 6   │ dwundrtxjv@upcomers.com  │ 288230376155014433│ Manual SL/TP │ -$64.87 (flt)   │
│ Acc 7   │ 875do5esrd@upcomers.com  │ 288230376155014438│ Manual SL/TP │ -$62.98 (flt)   │
│ Acc 8   │ h4sj53tg4f@upcomers.com  │ 288230376155014435│ Manual SL/TP │ -$63.02 (flt)   │
├─────────┴──────────────────────────┴──────────────────┴──────────────┼─────────────────┤
│ TOTAL REALIZED LOSSES (Accounts 1-3):                                │ -$158.23        │
│ FLOATING DRAWDOWN AT TIME OF DISCOVERY (Accounts 4-8):               │ -$323.53        │
├──────────────────────────────────────────────────────────────────────┼─────────────────┤
│ 💥 COMBINED FLEET IMPACT:                                            │ -$481.76 USD    │
└──────────────────────────────────────────────────────────────────────┴─────────────────┘
```

---

## 5. Architectural Safeguards Implemented

To permanently eliminate this vulnerability, the following changes have been committed directly to the core trading codebase in `src/clients/tl_client.py`:

### Safeguard 1: Mandatory In-Place Bracket Modification
Added `TradeLockerHelper.modify_position_bracket()` and `TradeLockerClient.update_fleet_stop_loss()`:
```python
def modify_position_bracket(self, position_id, stop_loss=None, take_profit=None):
    """
    Updates Stop Loss and Take Profit on an existing open position in place via PATCH.
    Guaranteed to NEVER place duplicate or orphan pending orders on the broker book.
    """
    if not self.access_token and not self.login():
        return False
    url = f"{self.base_url}/backend-api/trade/accounts/{self.account_id}/positions/{position_id}"
    payload = {"stopLossType": "absolute", "takeProfitType": "absolute"}
    if stop_loss is not None: payload["stopLoss"] = float(stop_loss)
    if take_profit is not None: payload["takeProfit"] = float(take_profit)
    return requests.patch(url, json=payload, headers=self._get_headers(auth=True), timeout=8)
```

### Safeguard 2: Direct Position Termination Endpoint
Added `TradeLockerHelper.close_position()` and `TradeLockerClient.close_all_fleet_positions()`:
* Explicitly calls `DELETE /backend-api/trade/accounts/{account_id}/positions/{position_id}`.
* Eliminates the dangerous pattern of sending opposing market orders to flatten accounts.

### Safeguard 3: Prohibition Rule
* **RULE:** `POST /orders` is **strictly prohibited** for updating existing positions. Any SL, TP, or trailing stop logic must route through `PATCH /positions/{pos_id}`.
* No scratch script or runner may create pending stop orders (`type: "stop"`) as a proxy for position protection.

---

## 6. Lessons Learned & Action Items
1. **Never send opposing market orders to close positions in a hedging environment.**
2. **Never create pending stop orders when attempting to modify existing position brackets.**
3. **Always verify post-order position state via `GET /positions` after any order operation.**
4. **All historical and future scripts must use the standardized methods in `tl_client.py`.**
