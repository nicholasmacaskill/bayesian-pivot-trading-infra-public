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
    
    # Risk Management (VOLUME OPERATOR: 3%+ Monthly Target)
    RISK_PER_TRADE = 0.0045  # 0.45% (Optimized for Non-Punitive SMT - ~157% ROI)
    MAX_DRAWDOWN_LIMIT = 0.06  # 6%
    DAILY_TRADE_LIMIT = 2

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
    
    # Strategy Mode: "SNIPER" (Optimized for High Precision)
    STRATEGY_MODE = "SNIPER" # Options: SNIPER, WIDE_NET
    AI_THRESHOLD = 8.0  # High Confidence (Relaxed from 8.5)
    
    # Exit Parameters (Wide Net)
    TP1_R_MULTIPLE = 1.5  # Bank profit early
    TP2_R_MULTIPLE = 3.0  # Runner
    STOP_LOSS_ATR_MULTIPLIER = 2.0  # Breathing Room
    
    # Killzones
    KILLZONE_ASIA = (0, 4)  # UTC (Midnight - 4 AM) - Asian Session
    KILLZONE_LONDON = (7, 10)  # UTC (London Open)
    KILLZONE_NY_AM = None  # Merged into continuous session
    KILLZONE_NY_PM = None  # Merged into continuous session
    KILLZONE_NY_CONTINUOUS = (12, 20)  # UTC (7 AM - 3 PM EST) - Full NY trading session
    
    # Edge Optimization Parameters (VOLUME OPERATOR MODE - 4 Trades/Week)
    MIN_SMT_STRENGTH = 0.30  # Require strong multi-asset alignment (Optimized for Quality over Quantity)
    MIN_PRICE_QUARTILE = 0.0  # Discount
    MAX_PRICE_QUARTILE = 0.50 # Strict Discount (No Equilibrium Chasing)
    MIN_PRICE_QUARTILE_SHORT = 0.50 # Strict Premium (No Equilibrium Chasing)
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
    DB_PATH = "/data/smc_alpha.db" if os.path.exists("/data") else os.path.join(os.getcwd(), "smc_alpha.db")

    # Local Runner Parameters
    RUN_INTERVAL_MINS = 1

    @classmethod
    def get(cls, key, default=None):
        return getattr(cls, key, default)
