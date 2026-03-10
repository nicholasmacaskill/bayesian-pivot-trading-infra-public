"""
Config — Sovereign Edge Engine
================================
All runtime parameters are loaded from environment variables.
Sensitive thresholds (AI score cutoff, risk sizing, killzone timing) are
intentionally not hardcoded in this public mirror.

Copy `.env.example` and set the values for your own deployment.
"""

import os


class Config:
    # ── Symbols ───────────────────────────────────────────────────────────────
    SYMBOLS     = os.environ.get("SYMBOLS", "BTC/USD,ETH/USD,SOL/USD").split(",")
    ALT_SYMBOLS = os.environ.get("ALT_SYMBOLS", "").split(",")

    TIMEFRAME     = os.environ.get("TIMEFRAME", "5m")
    HTF_TIMEFRAME = os.environ.get("HTF_TIMEFRAME", "1h")

    # ── Risk Management ───────────────────────────────────────────────────────
    # Override via environment — defaults are intentionally omitted.
    RISK_PER_TRADE      = float(os.environ.get("RISK_PER_TRADE", "0.007"))
    MAX_DRAWDOWN_LIMIT  = float(os.environ.get("MAX_DRAWDOWN_LIMIT", "0.06"))
    DAILY_DRAWDOWN_LIMIT= float(os.environ.get("DAILY_DRAWDOWN_LIMIT", "0.025"))
    DAILY_TRADE_LIMIT   = int(os.environ.get("DAILY_TRADE_LIMIT", "2"))
    TARGET_RR           = float(os.environ.get("TARGET_RR", "3.0"))

    # ── Prop Firm ─────────────────────────────────────────────────────────────
    ACTIVE_FIRM = os.environ.get("ACTIVE_FIRM", "FTMO")

    # ── Safety Toggles ────────────────────────────────────────────────────────
    USE_TRADELOCKER_API = os.environ.get("USE_TRADELOCKER_API", "true").lower() == "true"
    SYNC_AUTH_KEY       = os.environ.get("SYNC_AUTH_KEY", "")

    # ── Correlation & Calendar ────────────────────────────────────────────────
    CORRELATION_MAX_PER_DIRECTION = int(os.environ.get("CORRELATION_MAX_PER_DIRECTION", "1"))
    CORRELATION_SLOT_EXPIRY_HRS   = int(os.environ.get("CORRELATION_SLOT_EXPIRY_HRS", "4"))
    CALENDAR_BLACKOUT_MINUTES     = int(os.environ.get("CALENDAR_BLACKOUT_MINUTES", "30"))

    # ── AI Threshold (private — set via env) ─────────────────────────────────
    AI_THRESHOLD            = float(os.environ.get("AI_THRESHOLD", "7.0"))
    AI_THRESHOLD_ASIAN_FADE = float(os.environ.get("AI_THRESHOLD_ASIAN_FADE", "6.5"))

    # ── Database ──────────────────────────────────────────────────────────────
    DB_PATH = os.path.join(os.getcwd(), "data", "smc_alpha.db")

    # ── Runner ────────────────────────────────────────────────────────────────
    RUN_INTERVAL_MINS = int(os.environ.get("RUN_INTERVAL_MINS", "3"))

    # ── Ledger ────────────────────────────────────────────────────────────────
    LEDGER_ENABLED = os.environ.get("LEDGER_ENABLED", "true").lower() == "true"

    # ── Retraining ────────────────────────────────────────────────────────────
    RETRAIN_ENABLED      = os.environ.get("RETRAIN_ENABLED", "true").lower() == "true"
    RETRAIN_MIN_SAMPLES  = int(os.environ.get("RETRAIN_MIN_SAMPLES", "5"))
    RETRAIN_EXPORT_JSONL = os.environ.get("RETRAIN_EXPORT_JSONL", "true").lower() == "true"

    @classmethod
    def get(cls, key, default=None):
        return getattr(cls, key, default)
