import pandas as pd
import numpy as np
import sys
import os

# Add root to path for imports
SMC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SMC_ROOT)

from backtesting.backtest_utils import DataManager, VectorizedIndicators, NewsSimulator

class ComparativeBacktest:
    def __init__(self, symbol='BTC/USDT', days=30):
        self.symbol = symbol
        self.data_manager = DataManager()
        self.indicators = VectorizedIndicators()
        self.days = days
        self.df = None

    def prepare_data(self):
        if self.df is not None: return self.df
        
        # 1. Fetch Main Data
        df = self.data_manager.get_data(self.symbol, '5m', days=self.days)
        
        # 2. Fetch Correlation Data (DXY)
        dxy_df = self.data_manager.get_data("DXY", '5m', days=self.days)
        
        print("📊 Calculating Alpha Indicators...")
        df = self.indicators.add_atr(df)
        df = self.indicators.add_bias(df)
        df = self.indicators.add_session_ranges(df)
        
        # Support for SMT: Add recent highs/lows first
        df['recent_high'] = df['high'].rolling(20).max().shift(1)
        df['recent_low'] = df['low'].rolling(20).min().shift(1)
        
        df = self.indicators.add_regime_regime(df)
        df = self.indicators.add_smt_divergence(df, dxy_df)
        df = NewsSimulator.add_news_blackouts(df)
        
        # PHASE 3: Intraday Reversal Mastery
        df = self.indicators.add_displacement(df)
        df = self.indicators.add_mss(df)
        
        self.df = df
        return df

    def run_model(self, model_name, params):
        df = self.prepare_data()
        
        print(f"🚀 Running Model: {model_name}")
        killzone_hours = params['killzones']
        q_limit = params.get('q_limit', 0.25)
        
        trades = []
        
        # Filter candidates (Killzone + Bias + News + Regime)
        candidates = df[
            (df['hour'].isin(killzone_hours)) & 
            (df['bias'] != 'NEUTRAL') & 
            (df['news_blackout'] == False) &
            (df['hurst'] < 0.45)
        ]
        
        for idx, row in candidates.iterrows():
            bias = row['bias']
            
            # Quartile Check
            ref_high = row['asian_high'] if not pd.isna(row['asian_high']) else row['london_high']
            ref_low = row['asian_low'] if not pd.isna(row['asian_low']) else row['london_low']
            if pd.isna(ref_high): continue
            
            price_pos = (row['close'] - ref_low) / (ref_high - ref_low)
            if bias == 'BULLISH' and price_pos > q_limit: continue
            if bias == 'BEARISH' and price_pos < (1.0 - q_limit): continue
            
            # 3. Sweep/SMT Initial Hunt
            smt_bull = row['smt_bullish']
            smt_bear = row['smt_bearish']
            has_intent = False
            if bias == 'BULLISH' and (row['low'] < row['recent_low'] or smt_bull):
                has_intent = True
            elif bias == 'BEARISH' and (row['high'] > row['recent_high'] or smt_bear):
                has_intent = True
                
            if not has_intent: continue
            
            # 4. PHASE 3: REVERSAL CONFIRMATION (MSS + Displacement)
            confirmation = df.iloc[idx:idx+6]
            if confirmation.empty: continue
            
            is_confirmed = False
            for c_idx, c_row in confirmation.iterrows():
                if bias == 'BULLISH' and (c_row['mss_bullish'] or c_row['displaced']):
                    is_confirmed = True; break
                if bias == 'BEARISH' and (c_row['mss_bearish'] or c_row['displaced']):
                    is_confirmed = True; break
                    
            if not is_confirmed: continue
            
            # Simulate Outcome
            future = df.iloc[idx+1:idx+100]
            if future.empty: continue
            
            res = self.simulate_trade(bias, row['close'], row['atr'] * 1.5, 1.5, 3.0, future)
            trades.append(res)
            
        return trades

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

    def analyze(self, trades):
        if not trades: return {"Total Trades": 0, "Win Rate": "0%", "Total Return (R)": "0R"}
        df = pd.DataFrame(trades)
        wins = len(df[df['pnl_r'] > 0])
        total_r = df['pnl_r'].sum()
        return {
            "Total Trades": len(df),
            "Win Rate": f"{(wins/len(df)*100):.1f}%",
            "Total Return (R)": f"{total_r:.1f}R",
            "Expectancy (R/Trade)": f"{(total_r/len(df)):.2f}R"
        }

if __name__ == "__main__":
    runner = ComparativeBacktest(days=30)
    
    models = [
        ("London Only", {"killzones": range(7, 11)}),
        ("NY Only", {"killzones": range(12, 20)}),
        ("NY + Evening", {"killzones": list(range(12, 20)) + [0,1,2,3,4]}),
        ("All Major", {"killzones": list(range(7, 11)) + list(range(12, 20)) + [0,1,2,3,4]})
    ]
    
    print("\n" + "="*80)
    print(f"{'MODEL':<20} | {'TRADES':<10} | {'WIN RATE':<12} | {'TOTAL R':<10}")
    print("-" * 80)
    
    for name, params in models:
        trades = runner.run_model(name, params)
        stats = runner.analyze(trades)
        print(f"{name:<20} | {stats['Total Trades']:<10} | {stats['Win Rate']:<12} | {stats['Total Return (R)']:<10}")
    print("="*80)
