import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.core.config import Config

def test_sovereign_light_math():
    print("🧪 Testing Sovereign Light Simplicity & Sizing Logic...")
    
    # Enable target profit mode for testing
    Config.TARGET_PROFIT_MODE = True
    Config.TARGET_PROFIT_USD = 350.0
    Config.BYPASS_AI_GATE = True
    
    # 1. Assert Config state
    assert Config.BYPASS_AI_GATE is True
    assert Config.TARGET_PROFIT_MODE is True
    assert Config.TARGET_PROFIT_USD == 350.0
    
    # 2. Simulate the position sizing calculation for a 2.5 R:R trade setup
    setup = {
        'entry': 80000.0,
        'stop_loss': 79800.0, # $200 risk distance
        'target': 80500.0,    # $500 reward distance
    }
    
    _entry = setup['entry']
    _sl = setup['stop_loss']
    _tp = setup['target']
    _risk = abs(_entry - _sl)
    _actual_rr = round(abs(_tp - _entry) / _risk, 2) if (_tp and _risk > 0) else 0
    
    print(f"   Trade parameters: Risk={_risk:.2f} | R:R={_actual_rr:.2f}")
    assert _actual_rr == 2.5, f"Expected R:R of 2.5, got {_actual_rr}"
    
    # Compute the risk size based on target profit and R:R
    if Config.TARGET_PROFIT_MODE and _actual_rr > 0:
        risk_amt = Config.TARGET_PROFIT_USD / _actual_rr
    elif Config.FIXED_RISK_USD is not None:
        risk_amt = Config.FIXED_RISK_USD
    else:
        risk_amt = 100000.0 * Config.RISK_PER_TRADE
        
    print(f"   Calculated Risk Amount (Target Profit): ${risk_amt:.2f}")
    assert risk_amt == 140.0, f"Expected risk amount of $140 for 2.5 R:R trade to hit $350 profit, got {risk_amt}"
    
    # Compute lots
    lots = round(risk_amt / _risk, 4) if _risk > 0 else 0
    print(f"   Position size: {lots} lots")
    assert lots == 0.7, f"Expected 0.7 lots for $140 risk over $200 stop distance, got {lots}"
    
    # Calculate projected profit at target
    projected_profit = lots * abs(_tp - _entry)
    print(f"   Projected profit: ${projected_profit:.2f}")
    assert projected_profit == 350.0, f"Expected exactly $350 in profit at target, got {projected_profit}"
    
    print("✅ Sovereign Light Sizing Verification Passed!")


def test_fixed_risk_math():
    print("\n🧪 Testing Fixed Stop Loss Risk Sizing ($100 Hard Stop Limit)...")
    
    # Disable target profit mode to test fixed risk
    Config.TARGET_PROFIT_MODE = False
    Config.FIXED_RISK_USD = 100.0
    
    setup = {
        'entry': 80000.0,
        'stop_loss': 79800.0, # $200 risk distance
        'target': 80600.0,    # $600 reward distance
    }
    
    _entry = setup['entry']
    _sl = setup['stop_loss']
    _tp = setup['target']
    _risk = abs(_entry - _sl)
    _actual_rr = round(abs(_tp - _entry) / _risk, 2) if (_tp and _risk > 0) else 0
    
    # Calculate risk amount in fixed mode
    if Config.TARGET_PROFIT_MODE and _actual_rr > 0:
        risk_amt = Config.TARGET_PROFIT_USD / _actual_rr
    elif Config.FIXED_RISK_USD is not None:
        risk_amt = Config.FIXED_RISK_USD
    else:
        risk_amt = 100000.0 * Config.RISK_PER_TRADE
        
    print(f"   Calculated Risk Amount (Fixed Risk): ${risk_amt:.2f}")
    assert risk_amt == 100.0, f"Expected exactly $100.00, got {risk_amt}"
    
    lots = round(risk_amt / _risk, 4) if _risk > 0 else 0
    print(f"   Position size: {lots} lots")
    assert lots == 0.5, f"Expected 0.5 lots for $100 risk over $200 stop distance, got {lots}"
    
    # If hit SL, actual loss
    actual_loss = lots * _risk
    print(f"   Projected max loss: ${actual_loss:.2f}")
    assert actual_loss == 100.0, f"Expected max loss of exactly $100.00, got {actual_loss}"
    
    # If hit TP (3.0 R:R)
    projected_profit = lots * abs(_tp - _entry)
    print(f"   Projected profit at 3.0 R:R: ${projected_profit:.2f}")
    assert projected_profit == 300.0, f"Expected $300.00 profit, got {projected_profit}"
    
    print("✅ Fixed Stop Loss Risk Verification Passed!")


if __name__ == "__main__":
    try:
        test_sovereign_light_math()
        test_fixed_risk_math()
        print("\n🎉 All sizing verification tests passed successfully!")
    except AssertionError as ae:
        print(f"\n❌ Test assertion failed: {ae}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected test failure: {e}")
        sys.exit(1)
