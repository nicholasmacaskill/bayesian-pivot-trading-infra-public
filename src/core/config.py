import os

# Configure yfinance to use a local writable directory inside the workspace for its cache
try:
    import yfinance.cache as yf_cache
    workspace_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    workspace_cache = os.path.join(workspace_dir, "data", "yfinance_cache")
    os.makedirs(workspace_cache, exist_ok=True)
    yf_cache.set_cache_location(workspace_cache)
    yf_cache.set_tz_cache_location(workspace_cache)
    
    # Fallback to dummy caches to completely disable disk activity
    yf_cache._CookieCacheManager._Cookie_cache = yf_cache._CookieCacheDummy()
    yf_cache._ISINCacheManager._isin_cache = yf_cache._ISINCacheDummy()
    yf_cache._TzCacheManager._tz_cache = yf_cache._TzCacheDummy()
except Exception:
    pass


class Config:
    # Trading Parameters
    SYMBOLS = ['BTC/USD']  # Focus exclusively on BTC/USD (Proven System Edge)
    
    # Tier 2: High Alpha Altcoins (Judas Sweeps Only)
    ALT_SYMBOLS = []
    
    TIMEFRAME = '5m'
    HTF_TIMEFRAME = '1h'
    
    # Risk Management
    RISK_PER_TRADE = 0.001  # Proprietary (Redacted)  # 0.7% (Default)
    FIXED_RISK_USD = 100.0  # Defensive Mode: Hard cap at $100 per trade
    MAX_RISK_USD = 150.0    # Strict absolute risk cap per trade
    MAX_PROFIT_USD = 400.0  # Strict absolute profit cap per trade
    MAX_NOTIONAL_VALUE_USD = 50000.0  # Hard cap: max position value per trade
    MIN_STOP_LOSS_ATR = 1.5           # Minimum stop loss distance (ATR multiplier)
    # Minimum stop distance per asset as % of price (prevents tiny-ATR runaway lots)
    # e.g. BTC at $83k → min stop = $166; ATR must cause at least this distance
    MIN_STOP_PCT = {
        "BTC/USD": 0.002,   # 0.2% = ~$166 at $83k
        "ETH/USD": 0.002,   # 0.2% = ~$3.60 at $1,800
        "SOL/USD": 0.002,   # 0.2% = ~$0.24 at $120
    }
    # Minimum target distance per asset as % of price (prevents noise-level weekend ATR targets)
    MIN_TARGET_PCT = {
        "BTC/USD": 0.010,   # 1.0% = ~$640 at $64k
        "ETH/USD": 0.010,   # 1.0% = ~$35 at $3,500
        "SOL/USD": 0.015,   # 1.5% = ~$2.25 at $150
    }
    MAX_POSITION_SIZES = {
        "BTC/USD": 0.25,    # Capped at 0.25 BTC
        "ETH/USD": 27.0,    # ~$49k notional at $1,800
        "SOL/USD": 416.0,   # ~$50k notional at $120
    }
    MAX_DRAWDOWN_LIMIT = 0.05  # 6% Total Account Drawdown
    DAILY_DRAWDOWN_LIMIT = 0.025 # 2.5% Daily Drawdown
    DAILY_TRADE_LIMIT = 1
    TARGET_RR = 3.0
    
    # Prop Firm Execution Profiles
    ACTIVE_FIRM = "UPCOMERS"
    
    PROP_FIRMS = {"PUBLIC": {"name": "Public Profile", "url": "https://example.com", "contract_size": 1.0, "commission_rate": 0.0}},
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
    
    USE_TRADELOCKER_API = True
    SYNC_AUTH_KEY = os.environ.get("SYNC_AUTH_KEY", "")
    LIVE_AUTO_EXECUTION = os.environ.get("LIVE_AUTO_EXECUTION", "False").lower() == "true"

    # Sovereign Light Simplification Toggles (Defaults to simplified mode)
    BYPASS_AI_GATE = False        # Set to True to execute setups purely on Gates 1-5
    BYPASS_BIOMETRIC_GATE = True  # Set to True to ignore biometric stress halts
    
    # Target Profit Mode (Direct $300-$400 Clocking)
    TARGET_PROFIT_MODE = False     # Set to True to scale risk specifically for a target profit
    TARGET_PROFIT_USD = 350.0      # Target profit per trade (e.g. $300 - $400)

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
    AI_THRESHOLD_LONG = 8.0   # Leveled to match shorts (data shows longs avg $360 win vs $221)
    AI_THRESHOLD_SHORT = 8.0
    LONG_RISK_MULTIPLIER = 1.0  # Full size — longs earn it (55.1% win rate, +$5,849 net)
    AI_THRESHOLD = 9.0
    AI_THRESHOLD_ASIAN_FADE = 9.0
    
    # ── 98% Reliability Standard Thresholds ──────────────────────
    SYNC_PRICE_DELTA_MAX = 0.005     # 0.5% (Loosened for crypto volatility)
    SYNC_LATENCY_SEC_MAX = 120        # 2 Minutes
    SLIPPAGE_ATR_RATIO_MAX = 1.5      # Spread / ATR(14)
    HURST_CHAOS_RANGE = (0.45, 0.55)  # Must be rejected as CHOP / RANDOM
    HURST_MIN_MEMORY = 0.55          # Trending threshold
    HURST_MAX_RANDOM = 0.45          # Mean-reverting threshold
    
    # ── AI Risk Logic ──────────────────────────────────────────
    ROI_OPTIMIZATION_ENABLED = True
    TP1_RATIO = 0.5                    # 50% scale out
    BE_TRIGGER_R = 1.5                 # Move SL to entry at 1.5R
    AI_MIN_SMT_CONVERGENCE = 0.7       # Threshold for "Institutional Convergence"
    
    # ── Tiered Risk Scaling (Final 98% Standard) ──────────────
    AI_TRUST_TIER_AGGRESSIVE = 90      # Score 90+ -> 1.0% Risk
    AI_TRUST_TIER_CONSERVATIVE = 75    # Score 75-89 -> 0.5% Risk
    AI_TRUST_TIER_MINIMUM = 75         # < 75 -> 0% Risk (Monitor)
    # ──────────────────────────────────────────────────────────
    
    # Exit Parameters (Scalp Optimized)
    TP1_R_MULTIPLE = 2.5
    TP2_R_MULTIPLE = 4.0
    STOP_LOSS_ATR_MULTIPLIER = 2.5
    ENTRY_OFFSET_ATR_MULTIPLIER = 0.5
    
    # Killzones (UTC)
    KILLZONE_ASIA = (0, 0) # Redacted Timing
    KILLZONE_ASIAN_FADE = (0, 0) # Redacted Timing
    KILLZONE_LONDON = (0, 0) # Redacted Timing
    KILLZONE_NY_CONTINUOUS = (0, 0) # Redacted Timing
    
    # Edge Optimization
    MIN_SMT_STRENGTH = 0.99
    MIN_PRICE_QUARTILE = 0.0
    MAX_PRICE_QUARTILE = 0.0
    MIN_PRICE_QUARTILE_SHORT = 0.0
    MAX_PRICE_QUARTILE_SHORT = 0.0
    
    # Database Path (Local vs Modal Volume)
    DB_PATH = "/data/smc_alpha.db" if os.path.isdir("/data") else os.path.join(os.getcwd(), "data", "smc_alpha.db")

    # Local Runner Parameters
    RUN_INTERVAL_MINS = 3

    @classmethod
    def get(cls, key, default=None):
        return getattr(cls, key, default)

    @staticmethod
    def get_modal_secrets():
        import modal
        return [modal.Secret.from_name("smc-secrets")]
