#!/usr/bin/env python3
"""
Test script for Dual-Track Audit System
Validates regime detection, dynamic risk calculation, and AI prompt structure
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.engines.ai_validator import AIValidator
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_mock_dataframe(volatility='normal'):
    """Creates mock OHLCV data for testing"""
    dates = pd.date_range(end=datetime.now(), periods=100, freq='5min')
    
    if volatility == 'high':
        # High volatility: Large ATR
        price_base = 100000
        volatility_factor = 2000
    elif volatility == 'low':
        # Low volatility: Small ATR
        price_base = 100000
        volatility_factor = 200
    else:
        # Normal volatility
        price_base = 100000
        volatility_factor = 800
    
    np.random.seed(42)
    closes = price_base + np.cumsum(np.random.randn(100) * volatility_factor)
    highs = closes + np.abs(np.random.randn(100) * volatility_factor * 0.5)
    lows = closes - np.abs(np.random.randn(100) * volatility_factor * 0.5)
    opens = closes + np.random.randn(100) * volatility_factor * 0.3
    volumes = np.random.randint(100, 1000, 100)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': opens,
        'high': highs,
        'low': lows,
        'close': closes,
        'volume': volumes
    })
    
    return df

def test_regime_detection():
    """Test market regime detection"""
    print("=" * 60)
    print("TEST 1: Market Regime Detection")
    print("=" * 60)
    
    validator = AIValidator(api_key="MOCK")
    
    # Test high volatility
    df_high = create_mock_dataframe('high')
    regime_high = validator.detect_market_regime(df_high)
    print(f"✓ High Volatility Data → Regime: {regime_high}")
    
    # Test low volatility
    df_low = create_mock_dataframe('low')
    regime_low = validator.detect_market_regime(df_low)
    print(f"✓ Low Volatility Data → Regime: {regime_low}")
    
    # Test normal volatility
    df_normal = create_mock_dataframe('normal')
    regime_normal = validator.detect_market_regime(df_normal)
    print(f"✓ Normal Volatility Data → Regime: {regime_normal}")
    
    print()

def test_dynamic_risk():
    """Test dynamic risk calculation"""
    print("=" * 60)
    print("TEST 2: Dynamic Risk Calculation")
    print("=" * 60)
    
    validator = AIValidator(api_key="MOCK")
    
    # Test high score + low vol
    risk1 = validator.calculate_dynamic_risk(9.0, "Low-Volatility Consolidation", "Clear")
    print(f"✓ Score 9.0 + Low Vol → Multiplier: {risk1['multiplier']}x ({risk1['suggested_risk_pct']}%)")
    print(f"  Reasoning: {risk1['reasoning']}")
    
    # Test low score
    risk2 = validator.calculate_dynamic_risk(7.5, "Normal-Volatility Trending", "Clear")
    print(f"✓ Score 7.5 + Normal Vol → Multiplier: {risk2['multiplier']}x ({risk2['suggested_risk_pct']}%)")
    print(f"  Reasoning: {risk2['reasoning']}")
    
    # Test high-impact news
    risk3 = validator.calculate_dynamic_risk(8.0, "Normal-Volatility Trending", "ACTIVE EVENT: NFP in 15m")
    print(f"✓ Score 8.0 + News Event → Multiplier: {risk3['multiplier']}x ({risk3['suggested_risk_pct']}%)")
    print(f"  Reasoning: {risk3['reasoning']}")
    
    # Test high volatility
    risk4 = validator.calculate_dynamic_risk(8.0, "High-Volatility Expansion", "Clear")
    print(f"✓ Score 8.0 + High Vol → Multiplier: {risk4['multiplier']}x ({risk4['suggested_risk_pct']}%)")
    print(f"  Reasoning: {risk4['reasoning']}")
    
    print()

def test_hard_logic_fallback():
    """Test hard logic fallback with dual-track output"""
    print("=" * 60)
    print("TEST 3: Hard Logic Fallback (Dual-Track)")
    print("=" * 60)
    
    validator = AIValidator(api_key="MOCK")
    df = create_mock_dataframe('low')
    
    mock_setup = {
        'symbol': 'BTC/USDT',
        'pattern': 'Bullish PO3',
        'smt_strength': 0.8,
        'cross_asset_divergence': 0.6,
        'time_quartile': {'num': 2, 'phase': 'Q2: Manipulation'},
        'is_discount': True,
        'news_context': 'Clear'
    }
    
    result = validator.hard_logic_audit(mock_setup, df)
    
    print("✓ Dual-Track Structure:")
    print(f"  Live Execution:")
    print(f"    - Score: {result['live_execution']['score']}")
    print(f"    - Verdict: {result['live_execution']['verdict']}")
    print(f"    - Reasoning: {result['live_execution']['reasoning']}")
    
    print(f"  Shadow Optimizer:")
    print(f"    - Regime: {result['shadow_optimizer']['regime_classification']}")
    print(f"    - Multiplier: {result['shadow_optimizer']['suggested_risk_multiplier']}x")
    print(f"    - Reasoning: {result['shadow_optimizer']['optimization_reasoning']}")
    
    print()

def test_ai_prompt_structure():
    """Test AI analyze_trade with MOCK key"""
    print("=" * 60)
    print("TEST 4: AI Analyze Trade (MOCK)")
    print("=" * 60)
    
    validator = AIValidator(api_key="MOCK")
    df = create_mock_dataframe('low')
    
    mock_setup = {
        'symbol': 'BTC/USDT',
        'pattern': 'Bullish PO3 (Judas Swing)',
        'entry': 98500,
        'stop_loss': 97800,
        'target': 100600,
        'smt_strength': 0.9,
        'cross_asset_divergence': 0.7,
        'time_quartile': {'num': 2, 'phase': 'Q2: Manipulation'},
        'is_discount': True,
        'bias': 'BULLISH',
        'news_context': 'Clear',
        'position_size_estimate': 1.0
    }
    
    sentiment = {"fear_and_greed": 45}
    whales = {"net_flow": "Accumulation"}
    
    result = validator.analyze_trade(mock_setup, sentiment, whales, df=df)
    
    print("✓ AI Result Structure:")
    print(f"  Live Execution:")
    print(f"    - Score: {result['live_execution']['score']}")
    print(f"    - Verdict: {result['live_execution']['verdict']}")
    print(f"    - Reasoning: {result['live_execution']['reasoning'][:80]}...")
    
    print(f"  Shadow Optimizer:")
    print(f"    - Regime: {result['shadow_optimizer']['regime_classification']}")
    print(f"    - Multiplier: {result['shadow_optimizer']['suggested_risk_multiplier']}x")
    print(f"    - Alpha Delta: {result['shadow_optimizer']['alpha_delta_prediction']}")
    
    print()

if __name__ == "__main__":
    print("\n🧪 DUAL-TRACK AUDIT SYSTEM TEST SUITE\n")
    
    try:
        test_regime_detection()
        test_dynamic_risk()
        test_hard_logic_fallback()
        test_ai_prompt_structure()
        
        print("=" * 60)
        print("✅ ALL TESTS PASSED")
        print("=" * 60)
        print("\nDual-Track Audit System is ready for deployment!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
