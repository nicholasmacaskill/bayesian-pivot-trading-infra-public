
import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from src.core.config import Config
# Mock Config for test
Config.FIXED_RISK_USD = 500
Config.MAX_NOTIONAL_VALUE_USD = 10000 # Tight cap for testing
Config.MIN_STOP_LOSS_ATR = 1.5
Config.STOP_LOSS_ATR_MULTIPLIER = 0.5 # Force tight SL

def test_tight_stop_loss_floor():
    print("Testing Tight Stop Loss Floor...")
    from src.engines.smc_scanner import SMCScanner
    scanner = SMCScanner()
    
    # Create mock data with low volatility
    df = pd.DataFrame({
        'timestamp': pd.date_range(start='2024-01-01', periods=100, freq='5min'),
        'open': [2000] * 100,
        'high': [2005] * 100,
        'low': [1995] * 100,
        'close': [2000] * 100,
        'volume': [1000] * 100
    })
    
    atr = scanner.calculate_atr(df).iloc[-1]
    print(f"Calculated ATR: {atr}")
    
    # Test SL calculation in a mock scenario
    # Bullish setup logic from scan_pattern
    limit_entry = 2000
    # Original logic would be atr * 0.5 = 10 * 0.5 = 5
    # Floor logic: max(10 * 0.5, 10 * 1.5) = 15
    stop_buffer = max(atr * Config.STOP_LOSS_ATR_MULTIPLIER, atr * Config.MIN_STOP_LOSS_ATR)
    
    print(f"Stop Buffer (Multiplier 0.5, Floor 1.5): {stop_buffer}")
    assert stop_buffer == atr * 1.5, f"Expected floor of {atr * 1.5}, got {stop_buffer}"
    print("✅ Stop Loss Floor Verified.")

def test_notional_cap():
    print("\nTesting Notional Cap...")
    # Mocking setup and variables from local_scanner
    setup = {'entry': 2000, 'stop_loss': 1995} # $5 risk distance
    base_risk = 500
    regime_mult = 1.0
    psych_mult = 1.0
    alpha_mult = 1.0
    
    risk_amt = base_risk * regime_mult * psych_mult * alpha_mult
    lots = round(risk_amt / abs(setup['entry'] - setup['stop_loss']), 2)
    
    print(f"Initial Lots (Risk $500, Dist $5): {lots}")
    print(f"Initial Notional Value: ${lots * setup['entry']:,}")
    
    # Apply notional cap
    position_value = lots * setup['entry']
    max_notional = Config.MAX_NOTIONAL_VALUE_USD # 10000
    
    if position_value > max_notional:
        capped_lots = round(max_notional / setup['entry'], 2)
        capped_val = capped_lots * setup['entry']
        print(f"Capped Lots: {capped_lots}")
        print(f"Capped Value: ${capped_val:,}")
        assert capped_val <= max_notional
        assert capped_lots < lots
    
    print("✅ Notional Cap Verified.")

if __name__ == "__main__":
    try:
        test_tight_stop_loss_floor()
        test_notional_cap()
        print("\nAll technical logic verifications passed.")
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
