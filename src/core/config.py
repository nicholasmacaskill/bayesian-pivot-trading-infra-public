import os
from modal import Secret

class Config:
    # Trading Parameters
    SYMBOLS = ['BTC/USD', 'ETH/USD', 'SOL/USD']  # Tier 1: Institutional Majors (All Setups)
    
    # Tier 2: High Alpha Altcoins (Judas Sweeps Only)
    # Selected based on user's available watchlist (High Liquidity)
    ALT_SYMBOLS = []
    
    TIMEFRAME = '5m'
    HTF_TIMEFRAME = '1h'
    
    # Risk Management (VOLUME OPERATOR MODE)
    RISK_PER_TRADE = 0.007  # 0.7% (Scaled for optimized Volume Mode)
    MAX_DRAWDOWN_LIMIT = 0.06  # 6% Total Account Drawdown
    DAILY_DRAWDOWN_LIMIT = 0.025 # 2.5% Daily Drawdown (Standard Prop Rule)
    DAILY_TRADE_LIMIT = 2
    TARGET_RR = 3.0 # Minimum Average R:R Target

    # Prop Firm Execution Profiles
    ACTIVE_FIRM = "UPCOMERS"  # Options: STANDARD, UPCOMERS
    
    # Prop Firm Database (URLs for Auto-Scan)
    PROP_FIRMS = {
        "UPCOMERS": {
            "name": "Upcomers", 
            "url": "https://upcomers.com/faq", 
            "contract_size": 0.03, 
            "commission_rate": 0.005,
            "desc": "High Leverage / Micro Lots (Adversarial)"  
        },
        "FTMO": {
            "name": "FTMO", 
            "url": "https://ftmo.com/en/faq/", 
            "contract_size": 1.0, 
            "commission_rate": 0.001,
            "desc": "The Industry Standard (Safe)"
        },
        "FUNDEDNEXT": {
            "name": "FundedNext", 
            "url": "https://fundednext.com/faq", 
            "contract_size": 1.0, 
            "commission_rate": 0.001,
            "desc": "Balanced Growth"
        },
        "TOPSTEP": {
            "name": "TopStep", 
            "url": "https://intercom.help/topstep-llc/en/", 
            "contract_size": 1.0, 
            "commission_rate": 0.001,
            "desc": "Futures Focus"
        },
        "ALPHA_CAPITAL": {
            "name": "Alpha Capital", 
            "url": "https://alphacapitalgroup.uk/faq/", 
            "contract_size": 1.0, 
            "commission_rate": 0.001,
            "desc": "No Time Limits"
        },
        "THE5ERS": {
            "name": "The5ers", 
            "url": "https://the5ers.com/faqs/", 
            "contract_size": 1.0, 
            "commission_rate": 0.001,
            "desc": "Instant Funding"
        },
        "BLUE_GUARDIAN": {
            "name": "Blue Guardian", 
            "url": "https://blueguardian.com/faq", 
            "contract_size": 1.0, 
            "commission_rate": 0.001,
            "desc": "Low Slippage"
        },
        "E8_MARKETS": {"name": "E8 Markets", "url": "https://e8markets.com/faq", "contract_size": 1.0, "commission_rate": 0.001},
        "LARK_FUNDING": {"name": "Lark Funding", "url": "https://larkfunding.com/faq", "contract_size": 1.0, "commission_rate": 0.001},
        "FUNDING_PIPS": {"name": "Funding Pips", "url": "https://fundingpips.com/faq", "contract_size": 1.0, "commission_rate": 0.001},
        "GOAT_FUNDED": {"name": "Goat Funded", "url": "https://goatfundedtrader.com/faq", "contract_size": 1.0, "commission_rate": 0.001},
        "INSTANT_FUNDING": {"name": "Instant Funding", "url": "https://instantfunding.io/faq", "contract_size": 1.0, "commission_rate": 0.001},
        "MAVEN": {"name": "Maven Trading", "url": "https://maventrading.com/faq", "contract_size": 1.0, "commission_rate": 0.001},
        "AULA_FLOW": {"name": "AquaFunded", "url": "https://aquafunded.com/faq", "contract_size": 1.0, "commission_rate": 0.001},
        "MENT_FUNDING": {"name": "Ment Funding", "url": "https://mentfunding.com/faq", "contract_size": 1.0, "commission_rate": 0.001}
    }
    
    # Safety Toggles
    USE_TRADELOCKER_API = True  # Set to False to disable API sync and use mock values
    SYNC_AUTH_KEY = os.environ.get("SYNC_AUTH_KEY", "")  # Shared secret for Local -> Cloud push (MUST be set in .env.local)


    # ── Feature 1: Correlation Gate ───────────────────────────────────────────
    CORRELATION_MAX_PER_DIRECTION = 1  # Block if ≥ N signals in same direction per basket
    CORRELATION_SLOT_EXPIRY_HRS   = 4  # Auto-release slot after N hours (safety valve)

    CALENDAR_BLACKOUT_MINUTES = 30  # Block N minutes before AND after high-impact events
    NY_LUNCH_BLACKOUT = (17, 18)     # UTC (12 PM - 1 PM EST) - Institutional Manipulation Window

    # ── Feature 4: Regime Filter ─────────────────────────────────────────────
    REGIME_BLOCK_CHOPPY   = True   # Block signals in choppy regime
    REGIME_ADX_TREND_MIN  = 20     # ADX ≥ this = trending (Loosened from 25)
    REGIME_ADX_CHOPPY_MAX = 18     # ADX ≤ this + Hurst ≈ 0.5 = choppy

    # ── Feature 5: Signed Trade Ledger ───────────────────────────────────────
    LEDGER_ENABLED = True  # Cryptographically sign every signal (strongly recommended)

    # ── Feature 6: Automated Retraining ──────────────────────────────────────
    RETRAIN_ENABLED          = True  # Run weekly retraining loop
    RETRAIN_MIN_SAMPLES      = 5     # Minimum outcomes before retraining
    RETRAIN_EXPORT_JSONL     = True  # Export JSONL for Vertex AI fine-tuning
    
    # Strategy Mode: "SNIPER" (Optimized for High Precision)
    STRATEGY_MODE = "VOLUME_OPERATOR" # Options: SNIPER, VOLUME_OPERATOR
    AI_THRESHOLD = 4.5              # Loosened from 5.5 for higher trade rate
    AI_THRESHOLD_ASIAN_FADE = 5.0   # Relaxed for the 100% win rate Asian Fade window
    
    # Exit Parameters (Wide Net)
    TP1_R_MULTIPLE = 2.5  # Bank profit later (Higher R/R requested)
    TP2_R_MULTIPLE = 4.0  # Runner expansion
    STOP_LOSS_ATR_MULTIPLIER = 2.0  # Breathing Room
    
    # Killzones
    KILLZONE_ASIA = (0, 4)          # UTC (Midnight - 4 AM) → 7–11 PM EST Asian Session
    KILLZONE_ASIAN_FADE = (4, 7)    # UTC (4 AM - 7 AM)     → 11 PM – 2 AM EST ⭐ PRIME WINDOW (100% Win Rate)
    KILLZONE_LONDON = (7, 10)       # UTC (London Open)     → 2 AM – 5 AM EST
    KILLZONE_NY_AM = None           # Merged into continuous session
    KILLZONE_NY_PM = None           # Merged into continuous session
    KILLZONE_NY_CONTINUOUS = (12, 20)  # UTC (7 AM - 3 PM EST) - Full NY trading session
    
    # Edge Optimization Parameters (VOLUME OPERATOR MODE - Loosened)
    MIN_SMT_STRENGTH = 0.25  # Loosened from 0.40 to capture more correlated moves
    MIN_PRICE_QUARTILE = 0.0  # Discount
    MAX_PRICE_QUARTILE = 0.75 # Relaxed from 0.65 (More room for expansion)
    MIN_PRICE_QUARTILE_SHORT = 0.25 # Relaxed from 0.35
    MAX_PRICE_QUARTILE_SHORT = 1.0
    
    # Secrets (Loaded from Modal Environment)
    @staticmethod
    def get_modal_secrets():
        return [
            Secret.from_name("smc-secrets"), 
            Secret.from_name("gemini-secret"),
            Secret.from_name("supabase-secret")
        ]


    # Database Path (Modal Volume)
    DB_PATH = "/data/smc_alpha.db" if os.path.exists("/data") else os.path.join(os.getcwd(), "data", "smc_alpha.db")

    # Local Runner Parameters
    RUN_INTERVAL_MINS = 3 # Increased from 1 to prevent Gemini 429 Rate Limits

    @classmethod
    def get(cls, key, default=None):
        return getattr(cls, key, default)
