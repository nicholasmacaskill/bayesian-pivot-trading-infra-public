import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os
import json

# Internal imports
from src.engines.smc_scanner import SMCScanner
from src.core.config import Config

class SovereignBacktestV2:
    def __init__(self, symbol="BTC/USDT", start_date="2025-06-01", end_date="2025-12-31"):
        self.symbol = symbol
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.timeframe = "5m"
        
        # Initialize Scanner
        self.scanner = SMCScanner()
        # Disable order book for backtest speed
        self.scanner.order_book_enabled = False
        
        self.trades = []
        self.current_backtest_time = None
        self._i_curr = 0 # Pointer for vectorized lookups
        
    def fetch_historical_data(self):
        """Fetches data using CCXT (Simulation of production data)."""
        print(f"📥 Fetching 6-month sweep for {self.symbol}...")
        import ccxt
        exchange = ccxt.binance()
        
        all_ohlcv = []
        since = int(self.start_date.timestamp() * 1000)
        end_ts = int(self.end_date.timestamp() * 1000)
        
        while since < end_ts:
            limit = 1000
            ohlcv = exchange.fetch_ohlcv(self.symbol, self.timeframe, since, limit)
            if not ohlcv: break
            all_ohlcv.extend(ohlcv)
            since = ohlcv[-1][0] + 1
            if len(ohlcv) < limit: break
            
        df = pd.DataFrame(all_ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df

    def resample_data(self, df, rule):
        """Resamples 5m data to higher timeframes for bias confirmation."""
        agg_dict = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        df_resampled = df.set_index('timestamp').resample(rule).agg(agg_dict).dropna().reset_index()
        return df_resampled

    def check_outcome(self, entry, stop, target, direction, df, entry_idx):
        """Verifies if trade hit target or stop first with ROI optimization (Scaling & BE)."""
        risk_dist = abs(entry - stop)
        if risk_dist == 0: return 'ERROR', 0, 0
        
        tp1_hit = False
        be_active = False
        current_stop = stop
        total_pnl = 0
        rem_size = 1.0  # Remaining position size
        
        max_candles = 288 # 24h
        for i in range(1, max_candles + 1):
            f_idx = entry_idx + i
            if f_idx >= len(df): break
            
            candle = df.iloc[f_idx]
            
            # --- ROI Optimization Logic ---
            # 1. Break-Even Trigger (1.5R)
            if not be_active:
                move_threshold = (entry + risk_dist * 1.5) if direction == 'LONG' else (entry - risk_dist * 1.5)
                if (direction == 'LONG' and candle['high'] >= move_threshold) or \
                   (direction == 'SHORT' and candle['low'] <= move_threshold):
                    be_active = True
                    current_stop = entry
            
            # 2. Partial Profit (TP1 at 2.0R)
            if not tp1_hit:
                tp1_threshold = (entry + risk_dist * 2.0) if direction == 'LONG' else (entry - risk_dist * 2.0)
                if (direction == 'LONG' and candle['high'] >= tp1_threshold) or \
                   (direction == 'SHORT' and candle['low'] <= tp1_threshold):
                    tp1_hit = True
                    total_pnl += 0.5 * 2.0  # Secured 0.5 size at 2.0R
                    rem_size = 0.5
            # ------------------------------
            
            if direction == "LONG":
                if candle['low'] <= current_stop:
                    # SL Hit
                    exit_r = (current_stop - entry) / risk_dist
                    total_pnl += rem_size * exit_r
                    return ('WIN' if total_pnl > 0 else 'LOSS'), total_pnl, i
                if candle['high'] >= target:
                    # Final TP Hit
                    exit_r = (target - entry) / risk_dist
                    total_pnl += rem_size * exit_r
                    return 'WIN', total_pnl, i
            else:
                if candle['high'] >= current_stop:
                    # SL Hit
                    exit_r = (entry - current_stop) / risk_dist
                    total_pnl += rem_size * exit_r
                    return ('WIN' if total_pnl > 0 else 'LOSS'), total_pnl, i
                if candle['low'] <= target:
                    # Final TP Hit
                    exit_r = (entry - target) / risk_dist
                    total_pnl += rem_size * exit_r
                    return 'WIN', total_pnl, i
        
        # Timeout
        exit_p = df.iloc[min(entry_idx + max_candles, len(df)-1)]['close']
        exit_r = (exit_p - entry) / risk_dist if direction == 'LONG' else (entry - exit_p) / risk_dist
        total_pnl += rem_size * exit_r
        return ('WIN' if total_pnl > 0 else 'LOSS'), total_pnl, max_candles

    def run(self, symbols=None):
        """Primary execution loop with Portfolio Support."""
        if not symbols:
            symbols = ['BTC/USDT', 'ETH/USDT']
            
        print(f"🚀 Initializing High-Alpha Portfolio Optimization: {symbols}")
        
        for symbol in symbols:
            self.symbol = symbol
            # 1. Fetch Data
            df = self.fetch_historical_data()
            if df.empty: continue
            
            # 2. Resample Data
            df_1h = self.resample_data(df, '1h')
            df_15min = self.resample_data(df, '15min')
            df_4h = self.resample_data(df, '4h')
            df_1d = self.resample_data(df, '1D')
            
            # --- Monkey Patching for Speed & Determinism ---
            ts_5min = df['timestamp'].values
            ts_15min = df_15min['timestamp'].values
            ts_1h = df_1h['timestamp'].values
            ts_4h = df_4h['timestamp'].values
            ts_1d = df_1d['timestamp'].values

            def mock_fetch_data(fetch_symbol, timeframe, limit=500):
                if timeframe == self.timeframe: target, ts_arr = df, ts_5min
                elif timeframe == '15min': target, ts_arr = df_15min, ts_15min
                elif timeframe == '1h': target, ts_arr = df_1h, ts_1h
                elif timeframe == '4h': target, ts_arr = df_4h, ts_4h
                else: target, ts_arr = df_1d, ts_1d
                
                idx = np.searchsorted(ts_arr, np.datetime64(self.current_backtest_time), side='right')
                start_idx = max(0, idx - limit)
                return target.iloc[start_idx:idx] # Return view
                
            self.scanner.fetch_data = mock_fetch_data
            
            # 3. Pre-calculate indicators
            print(f"📈 Pre-calculating indicators for {symbol}...")
            for d in [df, df_15min, df_1h, df_4h, df_1d]:
                d['ema_20'] = d['close'].ewm(span=20).mean()
                d['ema_50'] = d['close'].ewm(span=50).mean()
                d['ema_200'] = d['close'].ewm(span=200).mean()
                high_low = d['high'] - d['low']
                high_cp = abs(d['high'] - d['close'].shift())
                low_cp = abs(d['low'] - d['close'].shift())
                tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
                d['atr'] = tr.rolling(14).mean()
            
            # 4. Hurst Pre-calc
            print(f"📊 Pre-calculating Hurst for {symbol}...")
            hurst_vals = np.full(len(df), 0.5)
            closes = df['close'].values
            for i in range(500, len(df), 10):
                window = closes[i-500:i]
                try:
                    hurst_vals[i] = self.scanner.get_hurst_exponent(window)
                except: pass
            df['hurst_precalc'] = pd.Series(hurst_vals).interpolate()
            
            # 5. Global Bias Matrix (Vectorized)
            print(f"🧮 Vectorizing Bias for {symbol}...")
            timestamps = df['timestamp'].values
            df_4h_ts = df_4h['timestamp'].values
            df_1d_ts = df_1d['timestamp'].values
            c4h_e20, c4h_e50 = df_4h['ema_20'].values, df_4h['ema_50'].values
            c1d_e20, c1d_e50 = df_1d['ema_20'].values, df_1d['ema_50'].values
            h_vals = df['hurst_precalc'].values
            
            bias_vector = []
            for i in range(len(df)):
                ts = timestamps[i]
                idx_4h = np.searchsorted(df_4h_ts, ts, side='right') - 1
                idx_1d = np.searchsorted(df_1d_ts, ts, side='right') - 1
                if idx_4h < 0 or idx_1d < 0:
                    bias_vector.append("NEUTRAL")
                    continue
                e20_4h, e50_4h = c4h_e20[idx_4h], c4h_e50[idx_4h]
                e20_1d, e50_1d = c1d_e20[idx_1d], c1d_e50[idx_1d]
                hurst = h_vals[i]
                ema_conflict = (e20_4h > e50_4h and e20_1d < e50_1d) or (e20_4h < e50_4h and e20_1d > e50_1d)
                if 0.495 <= hurst <= 0.505:
                    if ema_conflict: bias_vector.append("NEUTRAL")
                    else: bias_vector.append("BULLISH" if e20_4h > e50_4h else "BEARISH")
                elif hurst > 0.5:
                    bias_vector.append("BULLISH" if e20_4h > e50_4h else "BEARISH")
                else:
                    bias_vector.append("BULLISH" if e20_4h > e50_4h else "BEARISH")
            
            self.bias_matrix = bias_vector
            self.scanner.get_detailed_bias = lambda *args, **kwargs: self.bias_matrix[self._i_curr]
            self.scanner.get_hurst_exponent = lambda x: df.iloc[self._i_curr]['hurst_precalc']
            
            # 3. Disable News/IO filters
            self.scanner.news.is_news_safe = lambda: (True, "Backtest", 0)
            self.scanner.intermarket.get_market_context = lambda: {"DXY": {"trend": "NEUTRAL", "strength": 0.0}}
            self.scanner.intermarket.calculate_cross_asset_divergence = lambda *args, **kwargs: 0.6
            
            # 6. Candidate Filter
            diffs = df['close'].diff(10).abs().values
            atr_vals = df['atr'].values
            candidate_indices = np.where(diffs > (atr_vals * 1.5))[0]
            candidate_indices = candidate_indices[candidate_indices > 500]
            
            # 7. Sweep
            print(f"🔍 Sweeping {len(candidate_indices)} setups for {symbol}...")
            for idx, i in enumerate(candidate_indices):
                self.current_backtest_time = df.iloc[i]['timestamp']
                self._i_curr = i
                
                result = self.scanner.scan_pattern(
                    self.symbol, timeframe=self.timeframe, 
                    provided_df=df.iloc[max(0, i-500):i+1],
                    current_time_override=self.current_backtest_time,
                    visual_check=False
                )
                
                if result:
                    setup = result[0] if isinstance(result, tuple) else result
                    outcome, pnl_units, hold = self.check_outcome(
                        setup['entry'], setup['stop_loss'], setup['target'], 
                        setup['direction'], df, i
                    )
                    self.trades.append({
                        'ts': self.current_backtest_time.isoformat(),
                        'symbol': symbol,
                        'dir': setup['direction'],
                        'pat': setup['pattern'],
                        'res': outcome,
                        'pnl': round(pnl_units, 2),
                        'hold': hold
                    })
        
        self.report()

    def report(self):
        """Generates performance summary."""
        if not self.trades:
            print("❌ No trades found.")
            return
            
        tdf = pd.DataFrame(self.trades)
        tdf['ts'] = pd.to_datetime(tdf['ts'])
        tdf = tdf.sort_values('ts')
        
        wins = len(tdf[tdf['res'] == 'WIN'])
        total = len(tdf)
        wr = (wins / total) * 100 if total > 0 else 0
        total_pnl = tdf['pnl'].sum()
        
        tdf['cum_pnl'] = tdf['pnl'].cumsum()
        running_max = tdf['cum_pnl'].cummax()
        max_dd = (tdf['cum_pnl'] - running_max).min()
        
        print("\n" + "="*50)
        print("🏛️ SOVEREIGN HIGH-ALPHA PORTFOLIO REPORT")
        print("="*50)
        print(f"Total Trades: {total} (Multi-Asset)")
        print(f"Win Rate:     {wr:.2f}%")
        print(f"Total Alpha:  {total_pnl:.2f} Units (1% Risk)")
        print(f"Avg per Trade: {tdf['pnl'].mean():.2f} Units")
        print(f"Max Drawdown: {max_dd:.2f} Units")
        print("="*50)
        
        # Save results
        tdf.to_json('portfolio_results.json', orient='records', date_format='iso')
        print("✅ Results saved to portfolio_results.json")

if __name__ == "__main__":
    backtester = SovereignBacktestV2()
    backtester.run(symbols=['BTC/USDT', 'ETH/USDT'])
