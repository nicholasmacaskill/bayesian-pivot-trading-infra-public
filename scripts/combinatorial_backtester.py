import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import itertools
import json
import os
import sys

sys.path.append(os.getcwd())
from src.engines.smc_scanner import SMCScanner

class CombinatorialBacktester:
    def __init__(self, symbol="BTC/USDT", start_date="2025-11-01", end_date="2025-11-04"):
        self.symbol = symbol
        self.start_date = datetime.strptime(start_date, "%Y-%m-%d")
        self.end_date = datetime.strptime(end_date, "%Y-%m-%d")
        self.timeframe = "5m"
        self.scanner = SMCScanner()
        self.scanner.order_book_enabled = False
        
        self.df = self.fetch_historical_data()
        self.indices_to_scan = []
        self._prepare_data()

    def fetch_historical_data(self):
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
        return df.drop_duplicates(subset='timestamp')

    def _prepare_data(self):
        df = self.df
        for d in [df]:
            d['ema_20'] = d['close'].ewm(span=20).mean()
            d['ema_50'] = d['close'].ewm(span=50).mean()
            tr = pd.concat([d['high'] - d['low'], abs(d['high'] - d['close'].shift()), abs(d['low'] - d['close'].shift())], axis=1).max(axis=1)
            d['atr'] = tr.rolling(14).mean()
            
        timestamps = df['timestamp'].tolist()
        for i in range(500, len(df) - 100):
            h = timestamps[i].hour
            if (0 <= h < 4) or (7 <= h < 10) or (12 <= h < 20):
                self.indices_to_scan.append(i)

    def check_outcome(self, entry, stop, target, direction, df, entry_idx):
        risk_dist = abs(entry - stop)
        if risk_dist == 0: return 'ERROR', 0
        rem_size = 1.0
        total_pnl = 0
        tp1_hit = False
        current_stop = stop
        
        for i in range(1, 288):
            if entry_idx + i >= len(df): break
            candle = df.iloc[entry_idx + i]
            
            # Simple TP1 / Stop logic for speed
            if not tp1_hit:
                tp1 = entry + risk_dist * 2.0 if direction == 'LONG' else entry - risk_dist * 2.0
                if (direction == 'LONG' and candle['high'] >= tp1) or (direction == 'SHORT' and candle['low'] <= tp1):
                    tp1_hit = True
                    total_pnl += 0.5 * 2.0
                    rem_size = 0.5
                    current_stop = entry

            if direction == "LONG":
                if candle['low'] <= current_stop: return ('WIN' if total_pnl>0 else 'LOSS'), total_pnl + rem_size * ((current_stop - entry) / risk_dist)
                if candle['high'] >= target: return 'WIN', total_pnl + rem_size * ((target - entry) / risk_dist)
            else:
                if candle['high'] >= current_stop: return ('WIN' if total_pnl>0 else 'LOSS'), total_pnl + rem_size * ((entry - current_stop) / risk_dist)
                if candle['low'] <= target: return 'WIN', total_pnl + rem_size * ((entry - target) / risk_dist)
        
        exit_p = df.iloc[min(entry_idx + 288, len(df)-1)]['close']
        return 'TIMEOUT', total_pnl + rem_size * ((exit_p - entry) / risk_dist if direction == 'LONG' else (entry - exit_p) / risk_dist)

    def configure_gates(self, comb):
        use_hurst, use_smt, use_bias, use_volume, use_news = comb
        
        # Hurst Mock
        if not use_hurst:
            self.scanner.get_hurst_exponent = lambda x: 0.5 # Random/Neutral
        else:
            self.scanner.get_hurst_exponent = SMCScanner.get_hurst_exponent.__get__(self.scanner)
            
        # SMT Mock
        if not use_smt:
            self.scanner.intermarket.calculate_cross_asset_divergence = lambda *args: 1.0
            self.scanner.intermarket.detect_true_smt = lambda *args: ("TRUE_SMT", 1.0)
        else:
            self.scanner.intermarket.calculate_cross_asset_divergence = lambda *args: 0.0
            self.scanner.intermarket.detect_true_smt = lambda *args: (None, 0.0)
            
        # VERY IMPORTANT: Mock API calls to prevent hanging
        self.scanner.intermarket.get_market_context = lambda: {"DXY": {"trend": "NEUTRAL", "strength": 0}}
            
        # Bias Mock
        if not use_bias:
            self.scanner.get_detailed_bias = lambda *args, **kwargs: "STRONG BULLISH STRONG BEARISH"
        else:
            self.scanner.get_detailed_bias = lambda *args, **kwargs: "NEUTRAL"
            
        # Volume Mock
        if not use_volume:
            self.scanner.calculate_volume_cluster = lambda *args: 2.0
            self.scanner.validate_sweep_depth = lambda *args: True
        else:
            self.scanner.calculate_volume_cluster = SMCScanner.calculate_volume_cluster.__get__(self.scanner)
            self.scanner.validate_sweep_depth = lambda *args: False
            
        # News Mock
        if not use_news:
            self.scanner.news.is_news_safe = lambda: (True, "Backtest", 0)
        else:
            self.scanner.news.is_news_safe = lambda: (True, "Backtest", 0) # News is usually True in backtest anyway

    def run_combination(self, comb):
        self.configure_gates(comb)
        df = self.df
        trades = []
        
        for idx in self.indices_to_scan:
            current_timestamp = df.iloc[idx]['timestamp']
            historical_slice = df.iloc[max(0, idx-500):idx+1].copy()
            
            try:
                setup = self.scanner.scan_pattern(
                    self.symbol, 
                    timeframe='5m', 
                    provided_df=historical_slice, 
                    current_time_override=current_timestamp,
                    visual_check=False
                )
            except Exception as e:
                setup = None
                
            if setup:
                setup = setup[0] if isinstance(setup, tuple) else setup
                outcome, pnl_units = self.check_outcome(
                    setup['entry'], setup['stop_loss'], setup['target'], 
                    setup['direction'], df, idx
                )
                trades.append(pnl_units)
                
        if not trades: return 0, 0, 0.0
        wins = sum(1 for t in trades if t > 0)
        total = len(trades)
        wr = wins / total
        total_pnl = sum(trades)
        
        # Calculate approximate sharpe
        returns = np.array(trades)
        sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(365) if len(returns)>1 and np.std(returns) > 0 else 0
        return total, wr, total_pnl, sharpe

    def run_all(self):
        print(f"Executing Grid Search for {self.symbol}...")
        results = []
        gates = [True, False]
        combinations = list(itertools.product(gates, repeat=5))
        
        for i, comb in enumerate(combinations):
            print(f"[{i+1}/{len(combinations)}] Testing combo: Hurst={comb[0]}, SMT={comb[1]}, Bias={comb[2]}, Vol={comb[3]}, News={comb[4]}", end="\r")
            # We mock the mock to be clean
            total, wr, pnl, sharpe = self.run_combination(comb)
            results.append({
                "Hurst": comb[0],
                "SMT": comb[1],
                "Bias": comb[2],
                "Volume": comb[3],
                "News": comb[4],
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
    backtester = CombinatorialBacktester()
    backtester.run_all()
