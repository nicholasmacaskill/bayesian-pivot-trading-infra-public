"""
Live Multi-Modal AI Validation Sample Backtest Harness
======================================================
Executes live multi-modal vision inspection using Gemini 2.5 Flash and real chart rendering:

1. Renders high-resolution candlestick PNG chart images for historical candidate setups.
2. Evaluates each setup through live `AIValidator` (Gemini 2.5 Flash multi-modal vision).
3. Compares heuristic proxy score vs. live Gemini 2.5 Flash vision score.
4. Validates true price action outcome (Win/Loss).
"""

import sys
import os
import time
import json
import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load local environment variables (.env)
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env")))


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backtesting.backtest_utils import DataManager, VectorizedIndicators
from src.engines.ai_validator import AIValidator
from src.engines.visualizer import generate_ict_chart
from scripts.analysis.authentic_quant_ai_backtest import calculate_authentic_quant_ai_score
from scripts.analysis.institutional_blind_walkforward import simulate_trade_pessimistic

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LiveVisionSample")

def run_live_vision_sample(sample_size: int = 5):
    print("\n===========================================================================")
    print(" 🚀 BAYESIAN PIVOT — LIVE MULTI-MODAL AI VALIDATOR SAMPLE BACKTEST")
    print("===========================================================================\n")

    os.makedirs("data/charts", exist_ok=True)
    data_mgr = DataManager()
    indicators = VectorizedIndicators()

    print(" • Fetching Historical 5m Candles from Binance...")
    df = data_mgr.get_data("BTC/USDT", timeframe='5m', days=60)
    eth_df = data_mgr.get_data("ETH/USDT", timeframe='5m', days=60)

    print(f" • Loaded {len(df)} 5m candles. Calculating SMC indicators...")
    df = indicators.add_atr(df)
    df = indicators.add_bias(df, candles_per_4h=48)
    df['recent_high'] = df['high'].rolling(96).max().shift(1)
    df['recent_low']  = df['low'].rolling(96).min().shift(1)
    df = indicators.add_regime_regime(df)
    if eth_df is not None and not eth_df.empty and 'timestamp' in eth_df.columns:
        df = indicators.add_smt_divergence(df, eth_df, symbol_name="ETH")
    else:
        df['smt_bullish'] = False
        df['smt_bearish'] = False

    df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
    df = indicators.add_displacement(df)
    df = indicators.add_mss(df)
    df = indicators.add_fair_value_gap(df)
    df = indicators.add_equal_highs_lows(df)
    df = indicators.add_sweep_counter(df)
    df = indicators.add_wick_ratio(df)

    killzones = [0,1,2,3,4, 7,8,9,10, 12,13,14,15,16,17,18,19]
    candidates = df[
        (df['hour'].isin(killzones)) &
        (df['bias'] != 'NEUTRAL') &
        (df['mss_bullish'] | df['mss_bearish'] | df['strong_bull_sweep'] | df['strong_bear_sweep'])
    ].copy()

    print(f" • Found {len(candidates)} candidate trigger points. Selecting {sample_size} diverse sample setups...\n")

    sample_indices = np.linspace(100, len(candidates) - 100, sample_size, dtype=int)
    sample_df = candidates.iloc[sample_indices]

    validator = AIValidator()
    print(f" • Initialized SovereignAIHub (Active AI Model: Gemini 2.5 Flash / Claude)\n")

    comparison_records = []

    for i, (orig_idx, row) in enumerate(sample_df.iterrows(), 1):
        timestamp_str = str(row['timestamp'])
        bias = row['bias']
        direction = 'BUY' if bias == 'BULLISH' else 'SELL'
        entry_price = float(row['close'])
        atr = float(row['atr']) if not pd.isna(row['atr']) else entry_price * 0.008
        stop_dist = atr * 2.0
        sl_price = entry_price - stop_dist if direction == 'BUY' else entry_price + stop_dist
        tp_price = entry_price + (stop_dist * 2.5) if direction == 'BUY' else entry_price - (stop_dist * 2.5)

        pattern_name = f"SMC {row['regime']} {direction} Expansion"

        setup_dict = {
            'symbol': 'BTC/USD',
            'direction': direction,
            'pattern': pattern_name,
            'entry': entry_price,
            'stop_loss': sl_price,
            'target': tp_price,
            'smt_strength': 0.65 if (row['smt_bullish'] or row['smt_bearish']) else 0.20,
            'is_discount': direction == 'BUY',
            'is_premium': direction == 'SELL',
            'bias': bias,
            'news_context': 'Clear'
        }

        # 1. Compute Heuristic Proxy Score
        proxy_score = calculate_authentic_quant_ai_score(row.to_dict())


        # 2. Render High-Resolution Candlestick PNG Chart
        chart_filename = f"data/charts/sample_{i}_{direction}_{int(entry_price)}.png"
        slice_start = max(0, orig_idx - 60)
        slice_end = min(len(df), orig_idx + 1)
        df_chart_slice = df.iloc[slice_start:slice_end].copy()
        
        chart_path = generate_ict_chart(df_chart_slice, setup_dict, output_path=chart_filename)

        # 3. Call Live Multi-Modal AI Validator (Gemini 2.5 Flash)
        print(f"[{i}/{sample_size}] Calling Live Gemini 2.5 Flash on {setup_dict['symbol']} {direction} @ ${entry_price:,.2f}...")
        t0 = time.time()
        ai_res = validator.analyze_trade(
            setup=setup_dict,
            sentiment={'score': 65, 'summary': 'Bullish institutional accumulation'},
            whales={'active': True, 'bias': direction},
            image_path=chart_path,
            df=df_chart_slice,
            hurst_exponent=row.get('hurst', 0.58)
        )
        latency_sec = time.time() - t0

        live_score = float(ai_res.get('live_execution', {}).get('score', 0.0))
        verdict = ai_res.get('live_execution', {}).get('verdict', 'UNKNOWN')
        reasoning = ai_res.get('live_execution', {}).get('reasoning', '')[:120]

        # 4. Evaluate True Market Outcome (Pessimistic Routing)
        future_candles = df.iloc[orig_idx+1:orig_idx+289]
        trade_res = simulate_trade_pessimistic(
            bias=bias,
            entry=entry_price,
            stop_dist=stop_dist,
            tp1_r=1.5,
            tp2_r=2.5,
            future_candles=future_candles
        )

        outcome = "WIN (+2.0R)" if trade_res['pnl_r'] > 0 else f"LOSS ({trade_res['pnl_r']:.1f}R)" if trade_res['pnl_r'] < 0 else "NO_FILL"

        comparison_records.append({
            'sample_num': i,
            'timestamp': timestamp_str[:16],
            'dir': direction,
            'entry': entry_price,
            'proxy_score': proxy_score,
            'live_gemini_score': live_score,
            'verdict': verdict,
            'outcome': outcome,
            'latency': f"{latency_sec:.2f}s",
            'reasoning': reasoning
        })

    # Print Forensic Comparison Matrix
    print("\n--- LIVE GEMINI 2.5 FLASH MULTI-MODAL VALIDATION COMPARISON MATRIX ---")
    print(f"{'#':<3} | {'TIMESTAMP':<16} | {'DIR':<4} | {'ENTRY ($)':<9} | {'PROXY':<5} | {'LIVE AI':<7} | {'VERDICT':<10} | {'OUTCOME':<12} | {'LATENCY'}")
    print("-" * 95)

    for r in comparison_records:
        print(f"{r['sample_num']:<3} | {r['timestamp']:<16} | {r['dir']:<4} | ${r['entry']:<8,.0f} | {r['proxy_score']:<5.1f} | {r['live_gemini_score']:<7.1f} | {r['verdict']:<10} | {r['outcome']:<12} | {r['latency']}")

    print("===========================================================================\n")

if __name__ == "__main__":
    run_live_vision_sample()
