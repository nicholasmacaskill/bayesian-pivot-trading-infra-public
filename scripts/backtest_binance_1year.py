#!/usr/bin/env python3
"""
1-Year Binance Historical Backtest
Uses CCXT to fetch real 5-minute crypto data and validate Monte Carlo assumptions.
"""
import sys
import os
sys.path.append(os.getcwd())

import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.core.config import Config
from src.engines.intermarket_engine import IntermarketEngine
from src.engines.ai_validator import AIValidator

def fetch_binance_ohlcv(symbol, timeframe='5m', days_back=365):
    """Fetch OHLCV data from Binance."""
    exchange = ccxt.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'future'}  # Use futures to match trading environment
    })
    
    # Convert symbol format: BTC/USD -> BTC/USDT
    binance_symbol = symbol.replace('/USD', '/USDT')
    
    print(f"📥 Fetching {binance_symbol} ({timeframe}, last {days_back} days)...")
    
    # Calculate timestamps
    end_time = exchange.milliseconds()
    start_time = end_time - (days_back * 24 * 60 * 60 * 1000)
    
    all_candles = []
    current_time = start_time
    
    while current_time < end_time:
        try:
            candles = exchange.fetch_ohlcv(
                binance_symbol,
                timeframe=timeframe,
                since=current_time,
                limit=1000  # Binance max
            )
            
            if not candles:
                break
            
            all_candles.extend(candles)
            current_time = candles[-1][0] + 1  # Move to next candle
            
            print(f"   Downloaded {len(all_candles)} candles...", end='\r')
            
        except Exception as e:
            print(f"\n   ⚠️ Error: {e}")
            break
    
    print(f"\n   ✅ Total candles: {len(all_candles)}")
    
    # Convert to DataFrame
    df = pd.DataFrame(all_candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    # df = df.rename(columns={'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'})
    
    return df

def calculate_atr(df, period=14):
    """Calculate ATR for stop loss sizing."""
    high = df['high']
    low = df['low']
    close = df['close']
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return atr

def simulate_trade(df, entry_idx, direction, entry_price, sl_price, tp_price):
    """Simulate a trade and return the outcome."""
    future_df = df.iloc[entry_idx+1:]
    
    for idx, row in future_df.iterrows():
        high = float(row['high'])
        low = float(row['low'])
        
        if direction == 'LONG':
            if low <= sl_price:
                return 'LOSS', -1.0
            if high >= tp_price:
                return 'WIN', 3.0
        else:  # SHORT
            if high >= sl_price:
                return 'LOSS', -1.0
            if low <= tp_price:
                return 'WIN', 3.0
    
    return 'OPEN', 0.0

def detect_order_block_setup(df, idx, intermarket_engine):
    """
    Simplified Order Block detection logic.
    Returns (direction, entry, sl, tp) or None.
    """
    if idx < 50:
        return None
    
    recent_high = df['high'].iloc[max(0, idx-20):idx].max()
    recent_low = df['low'].iloc[max(0, idx-20):idx].min()
    current_price = float(df['close'].iloc[idx])
    current_low = float(df['low'].iloc[idx])
    current_high = float(df['high'].iloc[idx])
    
    atr_series = df['high'] - df['low'] # Simple ATR substitute for speed
    atr = float(atr_series.iloc[max(0, idx-14):idx].mean())
    vol_sma = df['volume'].iloc[max(0, idx-20):idx].mean()
    current_vol = float(df['volume'].iloc[idx])
    
    # Extract index context from the row (DXY, NQ, TNX)
    index_context = {}
    for sym in ['DXY', 'NQ', 'TNX']:
        if f'{sym}_trend' in df.columns:
            index_context[sym] = {'trend': df[f'{sym}_trend'].iloc[idx]}

    # LONG Setup: Sweep of recent low + Displacement + Volume
    if current_low < recent_low and current_price > recent_low:
        if current_vol < vol_sma * 1.2: return None # Volume Filter
        
        smt_long = intermarket_engine.calculate_cross_asset_divergence('LONG', index_context)
        if smt_long >= Config.MIN_SMT_STRENGTH:
            entry = current_price
            sl = entry - (atr * Config.STOP_LOSS_ATR_MULTIPLIER)
            tp = entry + (entry - sl) * 3.0  # 3R
            
            return {
                'symbol': 'BTC/USD',
                'pattern': 'Bullish Judas Sweep',
                'direction': 'LONG',
                'entry': entry,
                'stop_loss': sl,
                'target': tp,
                'smt_strength': smt_long,
                'cross_asset_divergence': smt_long,
                'is_discount': True,
                'bias': 'BULLISH',
                'news_context': 'Clear',
                'time_quartile': {'num': 2, 'phase': 'Q2: Manipulation'},
                'price_quartiles': {},
                'position_size_estimate': 1.0
            }
    
    # SHORT Setup: Sweep of recent high + rejection
    if current_high > recent_high and current_price < recent_high:
        if current_vol < vol_sma * 1.2: return None # Volume Filter
        
        smt_short = intermarket_engine.calculate_cross_asset_divergence('SHORT', index_context)
        if smt_short >= Config.MIN_SMT_STRENGTH:
            entry = current_price
            sl = entry + (atr * Config.STOP_LOSS_ATR_MULTIPLIER)
            tp = entry - (sl - entry) * 3.0  # 3R
            
            return {
                'symbol': 'BTC/USD',
                'pattern': 'Bearish Judas Sweep',
                'direction': 'SHORT',
                'entry': entry,
                'stop_loss': sl,
                'target': tp,
                'smt_strength': smt_short,
                'cross_asset_divergence': smt_short,
                'is_premium': True,
                'bias': 'BEARISH',
                'news_context': 'Clear',
                'time_quartile': {'num': 2, 'phase': 'Q2: Manipulation'},
                'price_quartiles': {},
                'position_size_estimate': 1.0
            }
    
    return None

def run_backtest():
    print(f"🔬 1-YEAR BINANCE HISTORICAL BACKTEST (OPTIMIZED)")
    print(f"=" * 60)
    print(f"📋 Scanner Config: MIN_SMT_STRENGTH = {Config.MIN_SMT_STRENGTH}")
    print(f"📋 AI Threshold: {Config.AI_THRESHOLD}")
    print(f"=" * 60)
    
    symbols = ['BTC/USD', 'ETH/USD', 'SOL/USD']
    intermarket = IntermarketEngine()
    validator = AIValidator()  # NEW: AI validation layer
    
    all_trades = []
    signals_before_ai = 0
    signals_after_ai = 0
    
    for symbol in symbols:
        try:
            df = fetch_binance_ohlcv(symbol, timeframe='5m', days_back=365)
            
            # Fetch intermarket data for the same period
            print(f"📥 Fetching 1h intermarket indices for SMT (1-year history)...")
            import yfinance as yf
            tickers = {"DXY": "DX-Y.NYB", "NQ": "^IXIC", "TNX": "^TNX"}
            for name, ticker in tickers.items():
                print(f"   Downloading {name}...")
                idx_data = yf.download(ticker, period="1y", interval="1h", progress=False)
                if not idx_data.empty:
                    if isinstance(idx_data.columns, pd.MultiIndex):
                        idx_data.columns = idx_data.columns.get_level_values(0)
                    
                    # Fix timezone mismatch (localize to naive for join)
                    if idx_data.index.tz is not None:
                        idx_data.index = idx_data.index.tz_localize(None)
                    
                    # Calculate trend
                    idx_data[f'{name}_change'] = idx_data['Close'].pct_change()
                    idx_data[f'{name}_trend'] = idx_data[f'{name}_change'].apply(lambda x: "UP" if x > 0 else "DOWN")
                    
                    # Join with main df and forward fill to match 5m
                    df = df.join(idx_data[[f'{name}_trend']], rsuffix=f'_{name}')
            
            # Fill missing trends
            df.ffill(inplace=True)
            df.fillna("NEUTRAL", inplace=True)
            
            print(f"   Column check: {df.columns.tolist()[:10]}...")
            print(f"   Trend sample (DXY): {df['DXY_trend'].head(10).tolist()}")
            
        except Exception as e:
            print(f"   ❌ Failed to fetch {symbol}: {e}")
            continue
        
        print(f"\n📊 Scanning {symbol} ({len(df)} candles)...")
        setups_found = 0
        
        last_signal_idx = -100
        for idx in range(50, len(df) - 100):
            if idx < last_signal_idx + 50:  # 50-candle cool-off (approx 4 hours)
                continue
                
            if idx % 5000 == 0:
                print(f"   Progress: {idx}/{len(df)} candles scanned... Signals: {signals_before_ai}")
                
            setup = detect_order_block_setup(df, idx, intermarket)
            if setup:
                last_signal_idx = idx
                signals_before_ai += 1
                
                # NEW: AI VALIDATION LAYER (Match Production Pipeline)
                # Create mock sentiment/whale data for AI
                sentiment = {"fear_greed": 50, "social_volume": "medium"}
                whales = {"large_volume_detected": False}
                
                # Run AI validation on historical setup
                ai_result = validator.analyze_trade(
                    setup, 
                    sentiment, 
                    whales,
                    image_path=None,  # Skip chart generation for speed
                    df=df.iloc[max(0, idx-100):idx+1],  # Pass recent candles
                    exchange=None
                )
                
                ai_score = ai_result['live_execution']['score']
                ai_verdict = ai_result['live_execution']['verdict']
                
                import time
                time.sleep(1) # Rate limit protection for Gemini
                
                # Filter by AI threshold (Relaxed to 7.5 for backtest due to lack of visual/sentiment context)
                BACKTEST_AI_THRESHOLD = 7.0
                if ai_score < BACKTEST_AI_THRESHOLD or ai_verdict not in ["FLOW_GO", "HARD_LOGIC_PASS"]:
                    print(f"   [AI REJECT] Score: {ai_score} | Verdict: {ai_verdict} | Reason: {ai_result['live_execution']['reasoning'][:100]}...")
                    continue
                
                signals_after_ai += 1
                
                # Proceed with trade simulation - extract from dict
                direction = setup['direction']
                entry = setup['entry']
                sl = setup['stop_loss']
                tp = setup['target']
                outcome, r_multiple = simulate_trade(df, idx, direction, entry, sl, tp)
                
                print(f"   ✅ [Trade {signals_after_ai}] {symbol} {direction} at {entry:.2f} | AI: {ai_score} | Outcome: {outcome} ({r_multiple}R)")
                
                all_trades.append({
                    'symbol': symbol,
                    'timestamp': df.index[idx],
                    'direction': direction,
                    'entry': entry,
                    'outcome': outcome,
                    'r_multiple': r_multiple,
                    'ai_score': ai_score,  # NEW: Track AI score
                    'ai_verdict': ai_verdict
                })
                
                setups_found += 1
                if setups_found % 10 == 0:
                    print(f"   Found {signals_before_ai} raw signals, {signals_after_ai} passed AI filter...", end='\r')
        
        print(f"   ✅ Total setups: {setups_found}")
    
    # Analysis
    print(f"\n" + "=" * 60)
    print(f"📈 BACKTEST RESULTS")
    print(f"=" * 60)
    
    if not all_trades:
        print(f"\n✅ Total Raw Signals (Before AI): {signals_before_ai}")
        print("❌ No trades found in the 1-year window.")
        print("   This indicates the scanner criteria or AI filter may be too strict.")
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
    
    print(f"\n✅ Total Raw Signals (Before AI): {signals_before_ai}")
    print(f"✅ Total Signals After AI Filter: {total_trades}")
    print(f"📊 AI Filter Efficiency: {(1 - total_trades/signals_before_ai)*100:.1f}% filtered out")
    print(f"\n✅ Wins: {len(wins)} ({win_rate:.1f}%)")
    print(f"❌ Losses: {len(losses)}")
    print(f"⏳ Open (Incomplete): {len(open_trades)}")
    print(f"\n📊 Average R-Multiple (Raw): {avg_r:.2f}R")
    print(f"📊 Average R-Multiple (After 0.5% Commission): {adjusted_avg_r:.2f}R")
    
    # Projected Annual ROI
    trades_per_month = total_trades / 12
    trades_per_year = total_trades
    expected_annual_return = (adjusted_avg_r * Config.RISK_PER_TRADE) * trades_per_year
    
    print(f"\n🎯 Signals Per Day (Raw): {signals_before_ai/365:.1f}/day")
    print(f"🎯 Signals Per Day (After AI): {total_trades/365:.1f}/day")
    print(f"🎯 AI Acceptance Rate: {(total_trades/signals_before_ai)*100:.1f}%")
    print(f"\n🎯 Expected Annual ROI: {expected_annual_return*100:.2f}%")
    
    # Compare to Monte Carlo
    monte_carlo_roi = 157.0
    difference = expected_annual_return * 100 - monte_carlo_roi
    
    print(f"\n🔄 Monte Carlo Projection: {monte_carlo_roi:.0f}%")
    print(f"🔄 Backtest Projection: {expected_annual_return*100:.2f}%")
    print(f"🔄 Difference: {difference:+.2f}%")
    
    if abs(difference) < 50:
        print(f"\n✅ VALIDATION: Backtest confirms Monte Carlo assumptions (within ±50%)")
    else:
        print(f"\n⚠️ WARNING: Significant discrepancy detected.")
        if difference < 0:
            print(f"   Monte Carlo may be overly optimistic by ~{abs(difference):.0f}%")
        else:
            print(f"   Backtest suggests system may outperform Monte Carlo by ~{difference:.0f}%")

if __name__ == "__main__":
    run_backtest()
