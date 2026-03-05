import pandas as pd
import numpy as np
import sys
import os

# Add root to path for imports
SMC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SMC_ROOT)

from backtesting.backtest_utils import DataManager, VectorizedIndicators, NewsSimulator

class SniperBacktest:
    def __init__(self, symbol='BTC/USDT', days=30, timeframe='5m'):
        self.symbol = symbol
        self.data_manager = DataManager()
        self.indicators = VectorizedIndicators()
        self.days = days
        self.timeframe = timeframe
        # Candle multiplier: how many candles = 4 hours
        self.candles_per_4h = {'5m': 48, '15m': 16, '1h': 4, '4h': 1}.get(timeframe, 4)
        # Swing lookback in candles (20 × 4h periods)
        self.swing_window = 20 * self.candles_per_4h
        self.df = None

    def prepare_data(self):
        # 1. Fetch Main Data
        df = self.data_manager.get_data(self.symbol, self.timeframe, days=self.days)
        
        # 2. Fetch Correlation Data (DXY)
        dxy_df = self.data_manager.get_data("DXY", self.timeframe, days=self.days)
        
        print(f"📊 Calculating Alpha Indicators ({self.timeframe}, {self.days}d)...")
        df = self.indicators.add_atr(df)
        df = self.indicators.add_bias(df, candles_per_4h=self.candles_per_4h)
        df = self.indicators.add_session_ranges(df)
        
        # Support for SMT: Add recent highs/lows (scaled to TF)
        df['recent_high'] = df['high'].rolling(self.swing_window).max().shift(1)
        df['recent_low'] = df['low'].rolling(self.swing_window).min().shift(1)
        
        # Phase 4: 200-candle Hurst for accurate regime detection
        df = self.indicators.add_regime_regime(df)
        df = self.indicators.add_smt_divergence(df, dxy_df)
        df = NewsSimulator.add_news_blackouts(df)
        
        # Phase 3: Reversal indicators
        df = self.indicators.add_displacement(df)
        df = self.indicators.add_mss(df)
        
        # Phase 4: Fair Value Gap (for trending pullback entries)
        df = self.indicators.add_fair_value_gap(df)
        
        # Phase 5: Stop Cascade Detection
        df = self.indicators.add_equal_highs_lows(df)   # EQL liquidity pools
        df = self.indicators.add_sweep_counter(df)       # Multi-sweep cascade tracker
        df = self.indicators.add_wick_ratio(df)          # Sweep quality gating
        
        self.df = df
        return df

    def run_backtest(self, slippage_bps=5, risk_per_trade=0.005):
        df = self.prepare_data()
        
        print(f"\n🔀 Running DUAL-REGIME Backtest ({slippage_bps}bps slippage, {risk_per_trade*100}% risk)")
        print("   Mode 1 (H<0.45): Reversal — fade sweeps via MSS + Displacement")
        print("   Mode 2 (H>0.55): Trending — continuation pullbacks into FVG")
        
        # Trending mode gets wider targets since trends run further
        tp1_r_rev, tp2_r_rev = 1.5, 3.0   # Reversal
        tp1_r_trn, tp2_r_trn = 2.0, 4.0   # Trending
        
        trades = []
        equity = 100.0
        peak_equity = 100.0
        max_drawdown = 0.0
        reversal_count = 0
        trending_count = 0
        
        # Killzones: widened by 1h each side to capture early/late session volatility
        # Asia: 23-05 UTC, London: 06-11 UTC, NY: 11-20 UTC
        killzones = [23, 0,1,2,3,4,5, 6,7,8,9,10,11, 12,13,14,15,16,17,18,19,20]
        
        # Pre-filter: session + bias (news blackout removed — disabled in live system too)
        candidates = df[
            (df['hour'].isin(killzones)) &
            (df['bias'] != 'NEUTRAL')
            # regime != TRANSITION removed — widened Hurst eliminates dead zone
        ]
        
        print(f"⚙️  {len(candidates)} candidates across both regimes...")
        
        for idx, row in candidates.iterrows():
            bias = row['bias']
            regime = row['regime']
            smt_bull = row['smt_bullish']
            smt_bear = row['smt_bearish']
            
            # Apply slippage
            slip = slippage_bps / 10000
            
            # ─── MODE 1: REVERSAL (Mean-Reverting Markets) ─────────────────
            if regime == 'MEAN_REVERTING':
                # Quartile Gate: long from discount, short from premium
                ref_high = row['asian_high'] if not pd.isna(row.get('asian_high', float('nan'))) else row.get('london_high', float('nan'))
                ref_low  = row['asian_low']  if not pd.isna(row.get('asian_low', float('nan')))  else row.get('london_low', float('nan'))
                if pd.isna(ref_high) or ref_high == ref_low: continue
                
                price_pos = (row['close'] - ref_low) / (ref_high - ref_low)
                if bias == 'BULLISH' and price_pos > 0.40: continue   # Must be in lower 40%
                if bias == 'BEARISH' and price_pos < 0.60: continue   # Must be in upper 40%
                
                # Sweep intent
                has_intent = (bias == 'BULLISH' and (row['low'] < row['recent_low'] or smt_bull)) or \
                             (bias == 'BEARISH' and (row['high'] > row['recent_high'] or smt_bear))
                if not has_intent: continue
                
                # ── Phase 5: Stop Cascade Quality Filter ──────────────────
                # Gate A: Is this an EQL (Equal Highs/Lows) liquidity pool?
                #   If yes, boost confidence — far more stops are resting here
                is_liquidity_pool = (bias == 'BULLISH' and row.get('is_eql_low', False)) or \
                                    (bias == 'BEARISH' and row.get('is_eql_high', False))
                
                # Gate B: Has the cascade exhausted (2+ sweeps)?
                #   If yes, most retail stops are already cleared
                cascade_exhausted = (bias == 'BULLISH' and row.get('bull_sweep_exhaustion', False)) or \
                                    (bias == 'BEARISH' and row.get('bear_sweep_exhaustion', False))
                
                # Gate C: Is this a strong wick sweep (quality of clearance)?
                strong_wick = (bias == 'BULLISH' and row.get('strong_bull_sweep', False)) or \
                              (bias == 'BEARISH' and row.get('strong_bear_sweep', False))
                
                # At least ONE of the three quality conditions must hold
                # (EQL pool, OR cascade exhausted, OR strong wick)
                # This prevents entering on weak first-sweep fakeouts
                has_quality = is_liquidity_pool or cascade_exhausted or strong_wick
                if not has_quality: continue
                
                # MSS + Displacement confirmation (widened to 12 candles)
                confirmation = df.iloc[idx:idx+12]
                if confirmation.empty: continue
                is_confirmed = any(
                    (bias == 'BULLISH' and (r['mss_bullish'] or r['displaced'])) or
                    (bias == 'BEARISH' and (r['mss_bearish'] or r['displaced']))
                    for _, r in confirmation.iterrows()
                )
                if not is_confirmed: continue
                
                if np.random.random() < 0.10: continue  # missed alert
                entry = row['close'] * (1 + slip if bias == 'BULLISH' else 1 - slip)
                tp1_r, tp2_r = tp1_r_rev, tp2_r_rev
                reversal_count += 1
            
            # ─── MODE 2: TRENDING (Momentum Markets) ───────────────────────
            elif regime == 'TRENDING':
                # Gate: only trade WITH the trend direction
                if bias == 'BULLISH' and smt_bear: continue   # SMT divergence = abort
                if bias == 'BEARISH' and smt_bull: continue

                # Entry: price has pulled back INTO an active FVG
                if bias == 'BULLISH':
                    fvg_top = row.get('fvg_bull_top', float('nan'))
                    fvg_bot = row.get('fvg_bull_bot', float('nan'))
                    if pd.isna(fvg_top) or pd.isna(fvg_bot): continue
                    in_fvg = fvg_bot <= row['close'] <= fvg_top
                else:
                    fvg_top = row.get('fvg_bear_top', float('nan'))
                    fvg_bot = row.get('fvg_bear_bot', float('nan'))
                    if pd.isna(fvg_top) or pd.isna(fvg_bot): continue
                    in_fvg = fvg_bot <= row['close'] <= fvg_top

                if not in_fvg: continue

                # Quality gate: require DISPLACEMENT + MSS + SMT confluence
                # SMT ensures the broader macro environment supports the continuation
                lookback_start = max(0, idx - 12)
                recent_window = df.iloc[lookback_start:idx+1]
                had_displacement = recent_window['displaced'].any()
                if not had_displacement: continue

                if bias == 'BULLISH':
                    had_mss = recent_window['mss_bullish'].any()
                    has_smt = smt_bull   # DXY diverging = macro tailwind for BTC long
                else:
                    had_mss = recent_window['mss_bearish'].any()
                    has_smt = smt_bear
                if not had_mss: continue
                if not has_smt: continue  # SMT required for all trending entries

                if np.random.random() < 0.10: continue  # missed alert
                entry = row['close'] * (1 + slip if bias == 'BULLISH' else 1 - slip)
                tp1_r, tp2_r = tp1_r_trn, tp2_r_trn
                trending_count += 1
            
            else:
                continue
            
            # ─── SHARED SIMULATION ──────────────────────────────────────────
            future = df.iloc[idx+1:idx+100]
            if future.empty: continue
            
            atr = row['atr']
            stop_dist = atr * 1.5
            res = self.simulate_trade(bias, entry, stop_dist, tp1_r, tp2_r, future)
            if np.random.random() < 0.05: res['pnl_r'] = -1.0
            
            pnl_money = equity * risk_per_trade * res['pnl_r']
            equity += pnl_money
            
            if equity > peak_equity: peak_equity = equity
            dd = (peak_equity - equity) / peak_equity
            if dd > max_drawdown: max_drawdown = dd
            
            trades.append({
                'timestamp': row['timestamp'],
                'bias': bias,
                'regime': regime,
                'pnl_r': res['pnl_r'],
                'equity': equity,
                'smt': smt_bull or smt_bear
            })
        
        print(f"\n📊 Regime Split: {reversal_count} Reversal trades | {trending_count} Trending trades")
        self.results = trades
        return self.analyze_results(trades, equity, max_drawdown)

    def simulate_trade(self, bias, entry, stop_dist, tp1_r, tp2_r, future):
        is_long = bias == 'BULLISH'
        stop = entry - stop_dist if is_long else entry + stop_dist
        tp1 = entry + (stop_dist * tp1_r) if is_long else entry - (stop_dist * tp1_r)
        tp2 = entry + (stop_dist * tp2_r) if is_long else entry - (stop_dist * tp2_r)
        
        hit_tp1 = False
        for row in future.itertuples():
            if is_long:
                if row.low <= stop: return {'pnl_r': -1.0} if not hit_tp1 else {'pnl_r': 0.5 * tp1_r}
                if not hit_tp1 and row.high >= tp1: hit_tp1 = True; stop = entry
                if hit_tp1 and row.high >= tp2: return {'pnl_r': 0.5*tp1_r + 0.5*tp2_r}
            else:
                if row.high >= stop: return {'pnl_r': -1.0} if not hit_tp1 else {'pnl_r': 0.5 * tp1_r}
                if not hit_tp1 and row.low <= tp1: hit_tp1 = True; stop = entry
                if hit_tp1 and row.low <= tp2: return {'pnl_r': 0.5*tp1_r + 0.5*tp2_r}
        
        return {'pnl_r': 0}

    def analyze_results(self, trades, final_equity, max_drawdown):
        if not trades: return {"error": "No trades found within strict parameters"}
        df = pd.DataFrame(trades)

        wins   = df[df['pnl_r'] > 0]
        losses = df[df['pnl_r'] < 0]
        total  = len(df)
        win_rate = (len(wins) / total * 100) if total > 0 else 0

        avg_win  = wins['pnl_r'].mean()  if not wins.empty  else 0
        avg_loss = losses['pnl_r'].mean() if not losses.empty else 0
        expectancy = (win_rate/100 * avg_win) + ((1 - win_rate/100) * avg_loss)

        gross_profit = wins['pnl_r'].sum()
        gross_loss   = abs(losses['pnl_r'].sum())
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else float('inf')

        # Sharpe (annualised, assumes ~252 trading days / year)
        daily_returns = df.groupby(df['timestamp'].dt.date)['pnl_r'].sum() if 'timestamp' in df.columns else df['pnl_r']
        sharpe = (daily_returns.mean() / daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0

        # Consecutive win/loss streaks
        streaks = (df['pnl_r'] > 0).astype(int)
        max_consec_wins  = max((sum(1 for _ in g) for k, g in __import__('itertools').groupby(streaks) if k == 1), default=0)
        max_consec_loss  = max((sum(1 for _ in g) for k, g in __import__('itertools').groupby(streaks) if k == 0), default=0)

        # SMT breakdown
        smt_trades = df[df['smt'] == True]
        smt_wr = (len(smt_trades[smt_trades['pnl_r'] > 0]) / len(smt_trades) * 100) if not smt_trades.empty else 0

        # Regime breakdown
        rev = df[df['regime'] == 'MEAN_REVERTING']
        trn = df[df['regime'] == 'TRENDING']
        rev_wr = (len(rev[rev['pnl_r'] > 0]) / len(rev) * 100) if not rev.empty else 0
        trn_wr = (len(trn[trn['pnl_r'] > 0]) / len(trn) * 100) if not trn.empty else 0

        # Direction breakdown
        longs  = df[df['bias'] == 'BULLISH']
        shorts = df[df['bias'] == 'BEARISH']
        long_wr  = (len(longs[longs['pnl_r'] > 0])   / len(longs)  * 100) if not longs.empty  else 0
        short_wr = (len(shorts[shorts['pnl_r'] > 0])  / len(shorts) * 100) if not shorts.empty else 0

        return {
            "── OVERVIEW ────────────────────": "",
            "Total Trades":           total,
            "Win Rate":               f"{win_rate:.1f}%",
            "Return":                 f"{(final_equity - 100):.2f}%",
            "Final Equity":           f"${final_equity:.2f}",
            "── RISK METRICS ────────────────": "",
            "Max Drawdown":           f"{(max_drawdown * 100):.2f}%",
            "Profit Factor":          f"{profit_factor:.2f}",
            "Sharpe Ratio":           f"{sharpe:.2f}",
            "Expectancy (R)":         f"{expectancy:.3f}R per trade",
            "── TRADE QUALITY ───────────────": "",
            "Avg Win (R)":            f"+{avg_win:.2f}R",
            "Avg Loss (R)":           f"{avg_loss:.2f}R",
            "Gross Profit (R)":       f"+{gross_profit:.1f}R",
            "Gross Loss (R)":         f"-{gross_loss:.1f}R",
            "Max Consec Wins":        max_consec_wins,
            "Max Consec Losses":      max_consec_loss,
            "── REGIME BREAKDOWN ────────────": "",
            "Reversal Mode WR":       f"{rev_wr:.1f}% on {len(rev)} trades",
            "Trending Mode WR":       f"{trn_wr:.1f}% on {len(trn)} trades",
            "── DIRECTION BREAKDOWN ─────────": "",
            "Long Win Rate":          f"{long_wr:.1f}% on {len(longs)} trades",
            "Short Win Rate":         f"{short_wr:.1f}% on {len(shorts)} trades",
            "── SIGNAL QUALITY ──────────────": "",
            "SMT Confluence WR":      f"{smt_wr:.1f}% on {len(smt_trades)} trades",
        }

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("   BAYESIAN PIVOT — 1 YEAR WALK-FORWARD (Phase 5)")
    print("   Cascade Filter: EQL + Sweep Exhaustion + Wick Ratio")
    print("   Timeframe: 1H | Period: 365 Days | Risk: 0.5%")
    print("   Filter Level: CALIBRATED (wider quartile + 12-candle MSS window)")
    print("=" * 60)

    backtest = SniperBacktest(symbol='BTC/USDT', days=365, timeframe='1h')
    results = backtest.run_backtest(slippage_bps=5, risk_per_trade=0.005)
    print("\n📊 1-YEAR RESULTS (Phase 5 Cascade Detection):")
    print(json.dumps(results, indent=2))
