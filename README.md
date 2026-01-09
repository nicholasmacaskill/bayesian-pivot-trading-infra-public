# SovereignSMC Architecture 🧠💎

SovereignSMC is a bespoke, institutional-grade automated trading system. It synthesizes Inner Circle Trader (ICT) concepts with advanced AI validation and a stealth architecture to identify and vet high-probability setups in the crypto and forex markets.

## 📈 System Architecture & Objectives

**Target:** Consistent Monthly Growth | **Frequency:** Adaptive (Configurable) | **Risk:** Dynamic Position Sizing

This system features a modular architecture designed for **tick-level replay verification** and real-time execution. It combines rigorous technical screening with AI-driven "soft quality" assessment to filter out lower-probability setups that rigid algorithms typically miss.

**Multi-Account Support:** System aggregates equity from multiple TradeLocker accounts and calculates position sizing across combined capital.

### Core Capabilities
- **Backtest Engine:** Tick-level verification against historical data.
- **Trade Frequency:** Adaptive based on volatility and session rules.
- **Risk Management:** Automated position sizing with drawdown protection limits.
- **Equity Protection:** Circuit breakers for daily loss and maximum drawdown.

## 🛡️ The Sovereign Edge

This system is a one-of-one build featuring:

### 1. Double Quartile Alignment (Time & Price)
Unlike retail indicators that only look at price, this bot enforces "Institutional Synchronicity":
- **Time Quartiles**: Configurable session segmentation. The bot prioritizes the **Manipulation (Q2) / Judas Window**.
- **Price Quartiles**: The bot automatically maps the **Asian Range** and **London Range** into quadrants. Longs are validated in **Discount**, and shorts in **Premium** based on configurable thresholds.

### 2. AI Logic Synthesis (The Sovereign Gatekeeper)
Every technical setup is passed through a **Large Language Model (Gemini)** acting as the **Sovereign Gatekeeper**. It interprets:
- **Liquidity Inducement**: Is the move a fake-out or a real institutional sweep?
- **Global Confluence**: Cross-referencing whale movements, news sentiment (CryptoPanic), and market fear (Fear & Greed).
- **Hard Score Filtering**: Only setups scoring above a high confidence threshold (e.g., **7.5/10**) are sent to your Telegram.
- **Discipline Enforcement**: AI monitors drawdown status and warns against strategy drift.

### 3. Stealth Architecture (Security & Performance)
The bot is engineered to remain "invisible" to broker WAFs (Web Application Firewalls):
- **Request Fingerprinting**: Mimics a human-driven Chrome browser on macOS.
- **Surgical Frequency**: Scans at the exact close of 5-minute candles to minimize noise and avoid rate-limit flags.
- **Autonomous Cloud Sync**: Fully independent TradeLocker bridge that fetches real-time equity safely from the cloud.

## 🚀 Setup Guide

### 1. Prerequisites
- **Modal Account**: `pip install modal` && `modal setup`
- **Gemini API Key**: Get from Google AI Studio.
- **Telegram Bot**: Get token from @BotFather.

### 2. API Key Acquisition Guide

#### A. Gemini AI (The Brain)
- Go to [Google AI Studio](https://aistudio.google.com/).
- Click **"Get API Key"** on the sidebar.
- Create a new key and copy it into `GEMINI_API_KEY`.

#### B. Telegram (The Notifier)
- Open Telegram and search for **@BotFather**.
- Send `/newbot`, follow the name prompts, and copy the **HTTP API Token** into `TELEGRAM_BOT_TOKEN`.
- Search for **@userinfobot** in Telegram, send it a message, and copy your **Id** into `TELEGRAM_CHAT_ID`.

#### C. TradeLocker (The Execution)
- Check the **Welcome Email** from your Prop Firm (e.g., Funding Pips, FTMO).
- Copy the **Email**, **Password**, and the specific **Server URL** (e.g., `https://live.tradelocker.com`).

#### D. CryptoPanic (Market Sentiment)
- Go to [CryptoPanic API](https://cryptopanic.com/developers/api/).
- Register for a free account and copy your **API Token** into `CRYPTOPANIC_API_KEY`.

#### E. Whale Alert (Whale Tracking)
- Go to [Whale Alert Developers](https://whale-alert.io/developers).
- Sign up for a free plan and copy your **API Key** into `WHALE_ALERT_API_KEY`.

### 3. Configure Local Environment (`.env.local`)
Create or edit the `.env.local` file in the root directory. This file stores your keys locally so they are never sent to the cloud.

| Variable | Source | Purpose |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Google AI Studio | Powers the AI Mentor and Audits |
| `TELEGRAM_BOT_TOKEN` | @BotFather | Sends you trade alerts |
| `TELEGRAM_CHAT_ID` | @userinfobot | Your personal Telegram ID |
| `TL_EMAIL_A/B` | Prop Firm Email | Your TradeLocker logins |
| `TL_PASS_A/B` | Prop Firm Email | Your TradeLocker passwords |
| `SYNC_AUTH_KEY` | `config.py` | Secures the local-to-cloud bridge |

> [!CAUTION]
> Keep this file private. It contains your real passwords.

### 4. Deploy Backend
```bash
cd smc-alpha
modal deploy modal_app.py
```

### 5. Run Dashboard (Local)
```bash
cd dashboard
npm install
npm run dev
```

### 6. Start IP-Safe Sync
Run this on your home computer to keep the cloud updated securely:
```bash
python local_sync.py
```

## 🛡️ Risk Rules (Configurable)
- **Max Drawdown**: System halts trading if breached.
- **Daily Limit**: Configurable max trades per day.
- **Risk Per Trade**: Adjustable percentage (e.g., 0.5% - 1.0%).
- **Safety Toggle**: Set `USE_TRADELOCKER_API = False` in `config.py` to disable real-time account sync if you have compliance concerns.

## 🕵️‍♂️ The Glass Auditor (AI Journal)
Every trade you take is now automatically audited locally from your Home IP:
- **Discipline Grade**: Ranks execution 1-10.
- **Deviation Logic**: AI detects FOMO, Revenge, or Strategy Drift.
- **Mentor Feedback**: ICT Persona feedback directly in the dashboard.

## 📊 Evaluation Criteria & Logic

The system follows a strict hierarchical evaluation flow before sending any signal:

### 1. Technical Scanner Logic (Tier 1 Filters)
- **Hard Time Gate**: Continuous NY Session (UTC Adjusted). Outside this, the bot sleeps.
- **Price Quartiles**:
    - **Longs**: Valid in **Discount** zones.
    - **Shorts**: Valid in **Premium** zones.
- **Structure & Confluence**:
    - **SMT Divergence**: Checks for DXY-based institutional sponsorship.
    - **Liquidity Sweep**: Detects sweeps of Asian/London Range or Previous Day High/Low.
    - **Standard Deviation Targeting**: Profit targets set dynamic SD multiples of session range.

### 2. Institutional Confluence (External Data)
- **Whale Flow**: Integrates Whale Alert API to detect large exchange inflows/outflows that could precede a move.
- **Sentiment Engine**: Pulls the "Fear & Greed Index" to avoid trading "dumb money" extremes.
- **News Pulse**: Correlates technical setups with live CryptoPanic news feeds to ensure institutional sponsorship.

### 3. AI Mentor Validation (The Sovereign Gatekeeper)
The Gemini AI applies the final "Professional Grade" (Score 0.0-10.0):
- **Low Score**: Discarded. Reasoning: Likely "Inducement" or low-quality liquidity.
- **High Score**: Verified. Precision trade entry calculations (Entry, SL, Position Size) are triggered and sent to Telegram.

*Built by Antigravity.*
