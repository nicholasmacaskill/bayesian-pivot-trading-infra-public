# [PUBLIC PORTFOLIO VERSION]
# NOTE: Core proprietary logic and parameters have been redacted/standardized.
# This repository demonstrates architecture, not live trading alpha.

import os
from modal import Secret

class Config:
    # Trading Parameters
    SYMBOLS = ['BTC/USDT', 'ETH/USDT']  # Institutional heavyweights
    TIMEFRAME = '5m'
    HTF_TIMEFRAME = '4h'
    
    # Risk Management (VOLUME OPERATOR: 3%+ Monthly Target)
    RISK_PER_TRADE = 0.0065  # 0.65% (The "Golden Mean": Equilibrium between Growth and Safety)
    MAX_DRAWDOWN_LIMIT = 0.06  # 6%
    DAILY_TRADE_LIMIT = 2
    
    # Safety Toggles
    USE_TRADELOCKER_API = True  # Set to False to disable API sync and use mock values
    SYNC_AUTH_KEY = os.environ.get("SYNC_AUTH_KEY", "dummy_key")  # Shared secret for Local -> Cloud push (MUST be set in .env.local)
    
    # Strategy Mode: "WIDE NET" (Optimized for High Win Rate)
    STRATEGY_MODE = "WIDE_NET" # Options: SNIPER, WIDE_NET
    AI_THRESHOLD = None # [PROPRIETARY - COMMERCIAL LICENSE REQUIRED]  # Relaxed from 7.5 to allow "B-Grade" setups (Frequency Boost)
    
    # Exit Parameters (Wide Net)
    TP1_R_MULTIPLE = 1.5  # Bank profit early
    TP2_R_MULTIPLE = 3.0  # Runner
    STOP_LOSS_ATR_MULTIPLIER = 2.0  # Breathing Room
    
    # Killzones
    KILLZONE_LONDON = None  # Disabled (User requests NY Only for higher win rate)
    KILLZONE_NY_AM = None  # Merged into continuous session
    KILLZONE_NY_PM = None  # Merged into continuous session
    KILLZONE_NY_CONTINUOUS = (12, 20)  # UTC (7 AM - 3 PM EST) - Full NY trading day
    
    # Edge Optimization Parameters (VOLUME OPERATOR MODE - 4 Trades/Week)
    MIN_SMT_STRENGTH = None # [PROPRIETARY - COMMERCIAL LICENSE REQUIRED]  # Moderate SMT allowed (0.3+ is valid)
    MIN_PRICE_QUARTILE = 0.0  # Discount
    MAX_PRICE_QUARTILE = 0.55 # Relaxed from 0.45 (Allows Equilibrium Trades)
    MIN_PRICE_QUARTILE_SHORT = 0.45 # Relaxed from 0.55 (Allows Equilibrium Trades)
    MAX_PRICE_QUARTILE_SHORT = 1.0
    
    # Secrets (Loaded from Modal Environment)
    @staticmethod
    def get_modal_secrets():
        return [Secret.from_name("smc-secrets")]


    # Database Path (Modal Volume)
    DB_PATH = "/data/smc_alpha.db" if os.path.exists("/data") else os.path.join(os.getcwd(), "smc_alpha.db")
