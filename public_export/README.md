# Sovereign SMC (Public Portfolio Edition)

**A Cloud-Native Quantitative Trading Engine with Multi-Modal AI Validation.**

> *Note: This repository is a sanitized release of a live production system. Proprietary alpha parameters, specific entry logic, and Oracle Knowledge Base prompts have been redacted to protect intellectual property.*

## 📦 Open Source Modules

This project contains standalone packages developed for the community:

*   **[tradelocker-python](./tradelocker-python)**: An unofficial Python client for automating TradeLocker accounts (Auth, Headers, Multi-Account Aggregation).

## 🦅 System Overview

Sovereign SMC is an event-driven algorithmic trading system designed to capture institutional liquidity sweeps during the New York Session. It moves beyond simple "indicator" logic by integrating:

1.  **Statistical Arbitrage:** Relies on structural market inefficiencies (Liquidity Pools) with >50,000 Monte Carlo simulations backing the risk profile.
2.  **Multi-Modal AI Validation:** Utilizes Google Gemini 2.0 Flash (Vision + Text) to visually inspect chart structure and validate "smart money" footprints against a proprietary knowledge base.
3.  **Institutional Intermarket Analysis:** Real-time correlation engine monitoring DXY (Dollar Index), Yields (TNX), and Equities (NQ/ES) to filter low-probability conditions.
4.  **Dynamic Volatility Adjustment:** Automatically shifts targeting logic based on real-time ATR (Average True Range) regimes.

## 🎯 Target Performance (Asymmetric Alpha Model)

The system is engineered for **Calculated Aggression**: accepting frequency risk to capture high-R outliers.

*   **Primary Objective:** Maximize Geometric Growth via Asymmetric Returns (3R+ Targets).
*   **Risk Profile:** Aggressive Entry Validation (0.65% Risk) with Tight Invalidation Points.
*   **Win Rate Philosophy:** Low Win Rate / High R:R acceptance (The "Sniper" Mindset).
*   **Drawdown:** < 6.0% Hard Limit (Optimization constraint, not fear).
*   **Edge:** Exploiting institutional liquidity sweeps before expansion phases.

> **Note:** These are target definitions based on the risk profile designed for rapid scaling.

## ⚡ Tech Stack

*   **Core Logic:** Python 3.10 (Pandas, NumPy, CCXT)
*   **Infrastructure:** Modal (Serverless Cloud Architecture)
*   **AI Layer:** Google Vertex AI / Gemini Pro Vision
*   **Execution:** TradeLocker API (Webhook-based limit orders)
*   **Notification:** Telegram Bot with Real-Time Rich Alerts

## 🛡️ Risk Management (The Fortress)

The system operates on a "Survival First" boolean logic:
*   **Hard Drawdown Limit:** Fixed circuit breakers at 6% global drawdown.
*   **News Filtering:** Automated calendar parsing to avoid High-Impact news events (CPI, FOMC).
*   **Correlation Guard:** Trading is suspended if safe-haven assets and risk assets decouple (Correlation Collapse protection).

## ⚠️ Disclaimer

This code is provided for educational and portfolio demonstration purposes only. The "Alpha" (profit-generating logic) has been removed. Running this unmodified will not result in profitable trades.