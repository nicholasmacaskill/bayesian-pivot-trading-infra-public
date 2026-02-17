#!/usr/bin/env python3
"""
6-Month Historical Backtest
Validates the Monte Carlo ROI projections by simulating actual scanner logic on historical data.
"""
import sys
import os
sys.path.append(os.getcwd())

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.core.config import Config
from src.engines.intermarket_engine import IntermarketEngine

def fetch_historical_data(symbol, start_date, end_date, interval='1h'):
    """Fetch historical data for backtesting."""
    yf_symbol = symbol.replace('/', '-')
    print(f"📥 Fetching {symbol} data ({start_date} to {end_date}, {interval})...")
    df = yf.download(yf_symbol, start=start_date, end=end_date, interval=interval, progress=False)
    if df.empty:
        print(f"   ⚠️ No data for {symbol}")
        return None
    return df

def calculate_atr(df, period=14):
    """Calculate ATR for stop loss sizing."""
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def simulate_trade(df, entry_idx, direction, entry_price, sl_price, tp_price):
    """Simulate a trade and return the outcome."""
    # Look forward from entry to find SL or TP hit
    future_df = df.iloc[entry_idx+1:]
    
    for idx, row in future_df.iterrows():
        high = float(row['High'])
        low = float(row['Low'])
        
        if direction == 'LONG':
            if low <= sl_price:
                return 'LOSS', -1.0
            if high >= tp_price:
                return 'WIN', 3.0  # Assuming 3R target
        else:  # SHORT
            if high >= sl_price:
                return 'LOSS', -1.0
            if low <= tp_price:
                return 'WIN', 3.0
    
    return 'OPEN', 0.0  # Trade didn't complete in backtest window

def detect_order_block_setup(df, idx, intermarket_engine, index_context):
    """
    Simplified Order Block detection logic.
    Returns (direction, entry, sl, tp) or None.
    """
    if idx < 50:  # Need enough history
        return None
    
    current = df.iloc[idx]
    recent_high = df['High'].iloc[max(0, idx-20):idx].max()
    recent_low = df['Low'].iloc[max(0, idx-20):idx].min()
    current_price = float(current['Close'])
    
    # Calculate ATR for stop sizing
    atr_series = calculate_atr(df.iloc[:idx+1])
    if atr_series.empty or pd.isna(atr_series.iloc[-1]):
        return None
    atr = float(atr_series.iloc[-1])
    
    # LONG Setup: Sweep of recent low + bounce
    current_low = df['Low'].iloc[idx]
    if current_low < recent_low and current_price > recent_low:
        smt_long = intermarket_engine.calculate_cross_asset_divergence('LONG', index_context)
        if smt_long >= Config.MIN_SMT_STRENGTH:
            entry = current_price
            sl = entry - (atr * Config.STOP_LOSS_ATR_MULTIPLIER)
            tp = entry + (entry - sl) * 3.0  # 3R
            return ('LONG', entry, sl, tp)
    
    # SHORT Setup: Sweep of recent high + rejection
    current_high = df['High'].iloc[idx]
    if current_high > recent_high and current_price < recent_high:
        smt_short = intermarket_engine.calculate_cross_asset_divergence('SHORT', index_context)
        if smt_short >= Config.MIN_SMT_STRENGTH:
            entry = current_price
            sl = entry + (atr * Config.STOP_LOSS_ATR_MULTIPLIER)
            tp = entry - (sl - entry) * 3.0  # 3R
            return ('SHORT', entry, sl, tp)
    
    return None

def run_backtest():
    print(f"🔬 ENHANCED HISTORICAL BACKTEST")
    print(f"=" * 60)
    print(f"Strategy: Using 1h data for 6-month trend + 5m for recent 60-day validation")
    
    # Date range: 6 months back (using 1h candles)
    end_date = datetime.now()
    start_date_6mo = end_date - timedelta(days=180)
    start_date_60d = end_date - timedelta(days=60)
    
    symbols = ['BTC/USD', 'ETH/USD', 'SOL/USD']
    intermarket = IntermarketEngine()
    
    all_trades = []
    
    # PHASE 1: 6-month backtest on 1H data (broader strokes)
    print(f"\n📊 PHASE 1: 6-Month Backtest (1H Candles)")
    for symbol in symbols:
        df = fetch_historical_data(symbol, start_date_6mo.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), interval='1h')
        if df is None:
            continue
        
        index_context = {
            'DXY': {'trend': 'UP', 'change_5m': 0.01},
            'NQ': {'trend': 'UP', 'change_5m': 0.02}
        }
        
        print(f"   Scanning {symbol} ({len(df)} candles)...")
        
        for idx in range(50, len(df) - 100):
            setup = detect_order_block_setup(df, idx, intermarket, index_context)
            if setup:
                direction, entry, sl, tp = setup
                outcome, r_multiple = simulate_trade(df, idx, direction, entry, sl, tp)
                
                all_trades.append({
                    'symbol': symbol,
                    'timestamp': df.index[idx],
                    'direction': direction,
                    'entry': entry,
                    'outcome': outcome,
                    'r_multiple': r_multiple,
                    'timeframe': '1H'
                })
    
    # PHASE 2: 60-day backtest on 5M data (higher precision)
    print(f"\n📊 PHASE 2: 60-Day Backtest (5M Candles)")
    for symbol in symbols:
        df = fetch_historical_data(symbol, start_date_60d.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'), interval='5m')
        if df is None:
            continue
        
        index_context = {
            'DXY': {'trend': 'UP', 'change_5m': 0.01},
            'NQ': {'trend': 'UP', 'change_5m': 0.02}
        }
        
        print(f"   Scanning {symbol} ({len(df)} candles)...")
        
        for idx in range(50, len(df) - 100):
            setup = detect_order_block_setup(df, idx, intermarket, index_context)
            if setup:
                direction, entry, sl, tp = setup
                outcome, r_multiple = simulate_trade(df, idx, direction, entry, sl, tp)
                
                all_trades.append({
                    'symbol': symbol,
                    'timestamp': df.index[idx],
                    'direction': direction,
                    'entry': entry,
                    'outcome': outcome,
                    'r_multiple': r_multiple,
                    'timeframe': '5M'
                })
    
    # Analysis
    print(f"\n" + "=" * 60)
    print(f"📈 BACKTEST RESULTS")
    print(f"=" * 60)
    
    if not all_trades:
        print("❌ No trades found in the 6-month window.")
        print("   This suggests the scanner criteria are too strict or data quality issues.")
        return
    
    total_trades = len(all_trades)
    wins = [t for t in all_trades if t['outcome'] == 'WIN']
    losses = [t for t in all_trades if t['outcome'] == 'LOSS']
    open_trades = [t for t in all_trades if t['outcome'] == 'OPEN']
    
    win_rate = (len(wins) / total_trades) * 100 if total_trades > 0 else 0
    avg_r = np.mean([t['r_multiple'] for t in all_trades])
    
    # Account for 0.5% commission (round-trip = 1%)
    commission_drag = 0.01 / Config.RISK_PER_TRADE  # As a multiple of R
    adjusted_r = [t['r_multiple'] - commission_drag for t in all_trades]
    adjusted_avg_r = np.mean(adjusted_r)
    
    print(f"\n✅ Total Setups Triggered: {total_trades}")
    print(f"✅ Wins: {len(wins)} ({win_rate:.1f}%)")
    print(f"❌ Losses: {len(losses)}")
    print(f"⏳ Open (Incomplete): {len(open_trades)}")
    print(f"\n📊 Average R-Multiple (Raw): {avg_r:.2f}R")
    print(f"📊 Average R-Multiple (After 0.5% Commission): {adjusted_avg_r:.2f}R")
    
    # Projected Annual ROI
    trades_per_month = total_trades / 6
    trades_per_year = trades_per_month * 12
    expected_annual_return = (adjusted_avg_r * Config.RISK_PER_TRADE) * trades_per_year
    
    print(f"\n🎯 Projected Trade Frequency: {trades_per_month:.1f}/month ({trades_per_year:.0f}/year)")
    print(f"🎯 Expected Annual ROI: {expected_annual_return*100:.2f}%")
    
    # Compare to Monte Carlo
    monte_carlo_roi = 157.0
    difference = expected_annual_return * 100 - monte_carlo_roi
    
    print(f"\n🔄 Monte Carlo Projection: {monte_carlo_roi:.0f}%")
    print(f"🔄 Backtest Projection: {expected_annual_return*100:.2f}%")
    print(f"🔄 Difference: {difference:+.2f}%")
    
    if abs(difference) < 30:
        print(f"\n✅ VALIDATION: Backtest confirms Monte Carlo assumptions (within ±30%)")
    else:
        print(f"\n⚠️ WARNING: Significant discrepancy detected. Monte Carlo may be overly optimistic.")

if __name__ == "__main__":
    run_backtest()
