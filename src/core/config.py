import os

class Config:
    # Trading Parameters
    SYMBOLS = ['BTC/USD', 'ETH/USD', 'SOL/USD']  # Tier 1: Institutional Majors (All Setups)
    
    # Tier 2: High Alpha Altcoins (Judas Sweeps Only)
    ALT_SYMBOLS = []
    
    TIMEFRAME = '5m'
    HTF_TIMEFRAME = '1h'
    
    # Risk Management
    RISK_PER_TRADE = 0.007  # 0.7%
    MAX_DRAWDOWN_LIMIT = 0.06  # 6% Total Account Drawdown
    DAILY_DRAWDOWN_LIMIT = 0.025 # 2.5% Daily Drawdown
    DAILY_TRADE_LIMIT = 2
    TARGET_RR = 3.0
    
    # Prop Firm Execution Profiles
    ACTIVE_FIRM = "UPCOMERS"
    
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
    USE_TRADELOCKER_API = True
    SYNC_AUTH_KEY = os.environ.get("SYNC_AUTH_KEY", "")

    # Correlation & Calendar
    CORRELATION_MAX_PER_DIRECTION = 1
    CORRELATION_SLOT_EXPIRY_HRS   = 4
    CALENDAR_BLACKOUT_MINUTES = 30
    NY_LUNCH_BLACKOUT = (17, 18)

    # Regime Filter
    REGIME_BLOCK_CHOPPY   = True
    REGIME_ADX_TREND_MIN  = 20
    REGIME_ADX_CHOPPY_MAX = 18

    # Signed Trade Ledger
    LEDGER_ENABLED = True

    # Automated Retraining
    RETRAIN_ENABLED          = True
    RETRAIN_MIN_SAMPLES      = 5
    RETRAIN_EXPORT_JSONL     = True
    
    # Strategy Mode
    STRATEGY_MODE = "VOLUME_OPERATOR"
    AI_THRESHOLD = 7.0
    AI_THRESHOLD_ASIAN_FADE = 6.5
    
    # Exit Parameters
    TP1_R_MULTIPLE = 2.5
    TP2_R_MULTIPLE = 4.0
    STOP_LOSS_ATR_MULTIPLIER = 2.0
    
    # Killzones (UTC)
    KILLZONE_ASIA = (0, 4)
    KILLZONE_ASIAN_FADE = (4, 7)
    KILLZONE_LONDON = (7, 10)
    KILLZONE_NY_CONTINUOUS = (12, 20)
    
    # Edge Optimization
    MIN_SMT_STRENGTH = 0.25
    MIN_PRICE_QUARTILE = 0.0
    MAX_PRICE_QUARTILE = 0.75
    MIN_PRICE_QUARTILE_SHORT = 0.25
    MAX_PRICE_QUARTILE_SHORT = 1.0
    
    # Database Path (Local)
    DB_PATH = os.path.join(os.getcwd(), "data", "smc_alpha.db")

    # Local Runner Parameters
    RUN_INTERVAL_MINS = 3

    @classmethod
    def get(cls, key, default=None):
        return getattr(cls, key, default)
