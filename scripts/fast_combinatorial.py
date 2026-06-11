import sys
import os
import itertools
import pandas as pd
import numpy as np

sys.path.append(os.getcwd())
from scripts.sovereign_backtest_v2 import SovereignBacktestV2

class FastCombinatorial(SovereignBacktestV2):
    def __init__(self):
        super().__init__(symbol="BTC/USDT", start_date="2025-10-01", end_date="2025-11-15")
        
    def run_grid(self):
        print(f"🚀 Initializing Fast Grid Search for {self.symbol}")
        df = self.fetch_historical_data()
        if df.empty: return
        
        # Pre-calc
        df_1h = self.resample_data(df, '1h')
        df_4h = self.resample_data(df, '4h')
        df_1d = self.resample_data(df, '1D')
        
        ts_5min = df['timestamp'].values
        ts_1h = df_1h['timestamp'].values
        ts_4h = df_4h['timestamp'].values
        ts_1d = df_1d['timestamp'].values

        def mock_fetch_data(fetch_symbol, timeframe, limit=500):
            if timeframe == self.timeframe: target, ts_arr = df, ts_5min
            elif timeframe == '1h': target, ts_arr = df_1h, ts_1h
            elif timeframe == '4h': target, ts_arr = df_4h, ts_4h
            else: target, ts_arr = df_1d, ts_1d
            idx = np.searchsorted(ts_arr, np.datetime64(self.current_backtest_time), side='right')
            start_idx = max(0, idx - limit)
            return target.iloc[start_idx:idx]
            
        self.scanner.fetch_data = mock_fetch_data
        
        for d in [df, df_1h, df_4h, df_1d]:
            d['ema_20'] = d['close'].ewm(span=20).mean()
            d['ema_50'] = d['close'].ewm(span=50).mean()
            tr = pd.concat([d['high'] - d['low'], abs(d['high'] - d['close'].shift()), abs(d['low'] - d['close'].shift())], axis=1).max(axis=1)
            d['atr'] = tr.rolling(14).mean()
            
        hurst_vals = np.full(len(df), 0.5)
        closes = df['close'].values
        for i in range(500, len(df), 10):
            try: hurst_vals[i] = self.scanner.get_hurst_exponent(closes[i-500:i])
            except: pass
        df['hurst_precalc'] = pd.Series(hurst_vals).interpolate()
        
        # Candidate Filter (All Killzones)
        diffs = df['close'].diff(10).abs().values
        atr_vals = df['atr'].values
        candidate_indices = np.where(diffs > (atr_vals * 0.5))[0] # Lowered threshold to get more sweeps
        candidate_indices = candidate_indices[candidate_indices > 500]
        
        # Valid Hours
        timestamps = df['timestamp'].values
        valid = []
        for i in candidate_indices:
            h = pd.Timestamp(timestamps[i]).hour
            if (0<=h<4) or (7<=h<10) or (12<=h<20): valid.append(i)
        candidate_indices = valid

        results = []
        combinations = list(itertools.product([True, False], repeat=4)) # Removing News for speed (always true)
        
        for i, comb in enumerate(combinations):
            use_hurst, use_smt, use_bias, use_volume = comb
            print(f"[{i+1}/{len(combinations)}] Testing: Hurst={use_hurst}, SMT={use_smt}, Bias={use_bias}, Vol={use_volume}", end="\r")
            self.trades = []
            
            # Mock Overrides
            self.scanner.get_hurst_exponent = lambda x: df.iloc[self._i_curr]['hurst_precalc'] if use_hurst else 0.5
            
            if not use_smt:
                self.scanner.intermarket.calculate_cross_asset_divergence = lambda *args: 1.0
                self.scanner.intermarket.detect_true_smt = lambda *args: ("TRUE_SMT", 1.0)
                self.scanner.intermarket.get_market_context = lambda: {"DXY": {"trend": "NEUTRAL", "strength": 0.0}}
            else:
                self.scanner.intermarket.calculate_cross_asset_divergence = lambda *args: 0.0
                self.scanner.intermarket.detect_true_smt = lambda *args: (None, 0.0)
                self.scanner.intermarket.get_market_context = lambda: {"DXY": {"trend": "NEUTRAL", "strength": 0.0}}
                
            if not use_bias:
                self.scanner.get_detailed_bias = lambda *args, **kwargs: "STRONG BULLISH STRONG BEARISH"
            else:
                self.scanner.get_detailed_bias = lambda *args, **kwargs: "BULLISH" # Simplified mock
                
            if not use_volume:
                self.scanner.calculate_volume_cluster = lambda *args: 2.0
                self.scanner.validate_sweep_depth = lambda *args: True
            else:
                self.scanner.calculate_volume_cluster = lambda *args: 0.5
                self.scanner.validate_sweep_depth = lambda *args: False
                
            self.scanner.news.is_news_safe = lambda: (True, "Backtest", 0)

            for idx in candidate_indices:
                self.current_backtest_time = df.iloc[idx]['timestamp']
                self._i_curr = idx
                try:
                    result = self.scanner.scan_pattern(
                        self.symbol, timeframe=self.timeframe, 
                        provided_df=df.iloc[max(0, idx-500):idx+1],
                        current_time_override=self.current_backtest_time,
                        visual_check=False
                    )
                except: result = None
                
                if result:
                    setup = result[0] if isinstance(result, tuple) else result
                    outcome, pnl_units, hold = self.check_outcome(
                        setup['entry'], setup['stop_loss'], setup['target'], 
                        setup['direction'], df, idx
                    )
                    self.trades.append(pnl_units)
                    
            wins = sum(1 for t in self.trades if t > 0)
            total = len(self.trades)
            wr = wins / total if total > 0 else 0
            pnl = sum(self.trades)
            returns = np.array(self.trades)
            sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(365) if len(returns)>1 and np.std(returns)>0 else 0
            
            results.append({
                "Hurst": use_hurst,
                "SMT": use_smt,
                "Bias": use_bias,
                "Volume": use_volume,
                "Trades": total,
                "WinRate": round(wr*100, 1),
                "TotalPnL": round(pnl, 2),
                "Sharpe": round(sharpe, 2)
            })

        print("\n")
        df_res = pd.DataFrame(results).sort_values("Sharpe", ascending=False)
        print(df_res.head(10).to_string())
        df_res.to_csv("combinatorial_results.csv", index=False)
        print("✅ Saved to combinatorial_results.csv")

if __name__ == "__main__":
    b = FastCombinatorial()
    b.run_grid()
