import sys
import os
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engines.smc_scanner import SMCScanner
from src.engines.intermarket_engine import IntermarketEngine

def test_phase2_logic():
    print("🧪 Testing Phase 2 Algorithmic Evolution...")
    
    scanner = SMCScanner()
    
    # 1. Test Volume Cluster Detection
    print("Checking Volume Cluster...")
    df_vol = pd.DataFrame({
        'volume': [10] * 19 + [50]  # Spike 5x
    })
    spike = scanner.calculate_volume_cluster(df_vol)
    print(f"Detected Spike: {spike}x")
    assert spike == 5.0
    
    # 2. Test True SMT Detection (Mocked Structure)
    print("Checking True SMT structure...")
    intermarket = IntermarketEngine()
    
    # Mock BTC structure: Higher Low (Bullish Refusal)
    # iloc[-10:-5] is indices 10-14. iloc[-5:] is indices 15-19.
    btc_df = pd.DataFrame({
        'high': [100] * 20,
        'low':  [100] * 10 + [80] * 5 + [95] * 5, # L1=80, L2=95. 95 > 80 (Higher Low)
        'close': [98] * 20
    })
    
    # Mock DXY structure: Higher High (Sweep)
    mock_dxy = pd.DataFrame({
        'High': [90] * 10 + [100] * 5 + [110] * 5, # H1=100, H2=110. 110 > 100 (Higher High)
        'Low': [80] * 20,
        'Close': [95] * 20
    })
    
    with patch('yfinance.download', return_value=mock_dxy):
        smt = intermarket.detect_true_smt(btc_df, "DXY")
        print(f"Detected SMT: {smt}")
        assert "BULLISH_SMT" in smt
        assert "DXY Sweep" in smt

    print("✅ Phase 2 Logic Verification Passed!")

if __name__ == "__main__":
    try:
        test_phase2_logic()
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
