# TradeLocker Python Client 📉

A lightweight, unofficial Python wrapper for automating **TradeLocker** accounts. This library simplifies authentication (JWT), session management, and data fetching for Prop Firm traders.

## 🛡️ Prop-Firm Safe Connectivity

The core value of this library is its **Stealth Connection Protocol**, designed specifically for Prop Firm environments that flag generic API bots.

*   **Biological Fingerprint:** Mimics a standard Chrome 121 browser session (`User-Agent`, `Origin`, `Referer`).
*   **WAF Evasion:** Bypasses "Bot Detected" screens by replicating organic login flows.
*   **Compliance Friendly:** Operates within standard "Human" rate limits and connection parameters.
*   **Multi-Account Aggregation:** Connects to multiple evaluation accounts simultaneously without triggering "Multiple IP" flags (uses single consistent session).

## 🚀 Features

*   **Automated Auth:** Handles JWT retrieval and token management transparently.
*   **Equity Tracking:** Real-time `get_equity()` monitoring for drawdown management.

## 📦 Installation

```bash
pip install tradelocker-python
# (Coming soon to PyPI, currently install from source)
```

## ⚡ Quick Start

### Single Account
```python
from tradelocker import TradeLockerSession

# Initialize Session
session = TradeLockerSession(
    email="user@example.com", 
    password="password123", 
    server="TRADELOCKER-DEMO", 
    base_url="https://demo.tradelocker.com"
)

# Connect and Print Equity
if session.login():
    print(f"Current Equity: ${session.get_equity()}")
```

### Multi-Account (Aggregation)
```python
from tradelocker import TradeLockerAggregator

agg = TradeLockerAggregator()

# Add multiple accounts
agg.add_session("acc1@test.com", "pass", "SERVER-A")
agg.add_session("acc2@test.com", "pass", "SERVER-B")

# Get total combine equity
print(f"Total Portfolio Value: ${agg.get_total_equity()}")
```

## ⚠️ Disclaimer
This is an unofficial client and is not affiliated with TradeLocker. Use at your own risk.
