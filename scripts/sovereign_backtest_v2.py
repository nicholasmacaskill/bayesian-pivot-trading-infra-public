import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import logging
import matplotlib
matplotlib.use('Agg') # Non-interactive backend
import matplotlib.pyplot as plt
from src.core.config import Config
from src.engines.smc_scanner import SMCScanner

# Configure simple logging for backtest
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

class SovereignBacktestV2:
    """
    Sovereign Truth Engine v2: 
    Supports 24/7 Global Liquidity Mode, Z-score Volume, and Hurst Calibration.
    """
    def __init__(self, symbol='BTC/USDT', start_date='2025-01-01', end_date='2026-01-01', timeframe='5m'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.timeframe = timeframe
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.scanner = SMCScanner()
        self.scanner.order_book_enabled = False # Disable L2 for backtest speed
        self.trades = []
        self.current_backtest_time = None
        
    def fetch_historical_data(self):
        """Fetches OHLCV data for the entire period."""
        print(f"📥 Fetching {self.symbol} data ({self.timeframe}) from {self.start_date} to {self.end_date}...")
        
        start_ts = int(datetime.strptime(self.start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(self.end_date, '%Y-%m-%d').timestamp() * 1000)
        
        all_data = []
        current_ts = start_ts
        
        while current_ts < end_ts:
            try:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, self.timeframe, since=current_ts, limit=1000)
                if not ohlcv:
                    break
                all_data.extend(ohlcv)
                current_ts = ohlcv[-1][0] + 1
                
                # Simple progress logging
                progress_date = datetime.fromtimestamp(current_ts / 1000).strftime('%Y-%m-%d')
                print(f"  ... fetched up to {progress_date}", end='\r')
            except Exception as e:
                print(f"\nError fetching data: {e}")
                break
                
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp').sort_values('timestamp').reset_index(drop=True)
        
        # Cast to numeric
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        print(f"\n✅ Data loaded: {len(df)} candles")
        if not df.empty:
            print(f"📊 Range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        return df

    def resample_data(self, df, timeframe):
        """Standard resample logic for higher timeframes."""
        # Pandas >= 2.0 uses lowercase: h, d, min
        rule = timeframe.lower().replace('m', 'min').replace('h', 'h').replace('d', 'd')
        if timeframe == '4h': rule = '4h'
        if timeframe == '1d': rule = '1d'
        
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
        """Verifies if trade hit target or stop first."""
        # Add 1bps slippage
        effective_entry = entry * 1.0001 if direction == "LONG" else entry * 0.9999
        
        # Max hold 24h (288 * 5m)
        max_candles = 288
        for i in range(1, max_candles + 1):
            f_idx = entry_idx + i
            if f_idx >= len(df): break
            
            candle = df.iloc[f_idx]
            if direction == "LONG":
                if candle['low'] <= stop: return 'LOSS', stop, i
                if candle['high'] >= target: return 'WIN', target, i
            else:
                if candle['high'] >= stop: return 'LOSS', stop, i
                if candle['low'] <= target: return 'WIN', target, i
        
        # Timeout at close of last candle
        return 'TIMEOUT', df.iloc[min(entry_idx + max_candles, len(df)-1)]['close'], max_candles

    def run(self):
        """Primary execution loop."""
        df = self.fetch_historical_data()
        if df.empty: return
        
        df_1h = self.resample_data(df, '1h')
        df_4h = self.resample_data(df, '4h')
        df_1d = self.resample_data(df, '1d')
        
        # --- Monkey Patching for Speed & Determinism ---
        
        # 1. Mock fetch_data to use local slices
        ts_5m = df['timestamp'].values
        ts_1h = df_1h['timestamp'].values
        ts_4h = df_4h['timestamp'].values
        ts_1d = df_1d['timestamp'].values

        def mock_fetch_data(symbol, timeframe, limit=500):
            if timeframe == '5m': target, ts_arr = df, ts_5m
            elif timeframe == '1h': target, ts_arr = df_1h, ts_1h
            elif timeframe == '4h': target, ts_arr = df_4h, ts_4h
            else: target, ts_arr = df_1d, ts_1d
            
            idx = np.searchsorted(ts_arr, np.datetime64(self.current_backtest_time), side='right')
            start_idx = max(0, idx - limit)
            return target.iloc[start_idx:idx].copy()
            
        self.scanner.fetch_data = mock_fetch_data
        
        # 2. Mock Intermarket (Symmetric/Neutral for Backtest)
        def mock_get_market_context():
            # Returns neutral context to let Price Action and Hurst dictate bias
            return {
                "NQ": {"trend": "NEUTRAL", "change_ltf": 0.0},
                "DXY": {"trend": "NEUTRAL", "change_ltf": 0.0},
                "TNX": {"trend": "NEUTRAL", "change_ltf": 0.0}
            }
        
        self.scanner.intermarket.get_market_context = mock_get_market_context
        
        # 3. Disable News/IO filters
        self.scanner.news.is_news_safe = lambda: (True, "Backtest", 0)
        
        # 4. Disable charts & Clear Caches
        import src.engines.smc_scanner
        src.engines.smc_scanner.generate_bias_chart = lambda *args, **kwargs: False
        self.scanner._bias_cache = {}
        
        # 5. Symmetric Divergence Mock
        self.scanner.intermarket.calculate_cross_asset_divergence = lambda direction, ctx: 0.6 if direction in ['LONG', 'SHORT'] else 0.0
        
        # 6. Ensure real-time filters don't block backtest
        self.scanner._signal_cache = {} 
        self.scanner._signal_cooldown_mins = 0
        
        print("🔍 Scanning 24/7 for institutional footprints...")
        start_idx = 500
        total_len = len(df)
        
        for i in range(start_idx, total_len - 300):
            self.current_backtest_time = df.iloc[i]['timestamp']
            
            if i % 100 == 0:
                print(f"  ... processing {self.current_backtest_time.strftime('%Y-%m-%d')} ({i}/{total_len})", end='\r')
            
            # Use real scanner logic
            # CRITICAL: the scanner relies on real-time cache which freezes backtests. We must flush the cache.
            if hasattr(self.scanner, '_bias_cache'):
                self.scanner._bias_cache.clear()

            result = self.scanner.scan_pattern(
                self.symbol,  
                timeframe='5m', 
                provided_df=df.iloc[max(0, i-500):i+1].copy(),
                current_time_override=self.current_backtest_time,
                visual_check=False
            )
            
            if result:
                setup = result[0] if isinstance(result, tuple) else result
                # Pass 'tp1' instead of the multi-day institutional 'target'
                outcome, exit_p, hold = self.check_outcome(
                    setup['entry'], setup['stop_loss'], setup['tp1'], 
                    setup['direction'], df, i
                )
                
                # Calculate PnL assuming 1% risk per trade
                # We normalize RR and risk 1 unit.
                risk_amt = abs(setup['entry'] - setup['stop_loss'])
                pnl_units = (exit_p - setup['entry']) / risk_amt if setup['direction'] == 'LONG' else (setup['entry'] - exit_p) / risk_amt
                
                self.trades.append({
                    'ts': self.current_backtest_time.isoformat(),
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
        wins = len(tdf[tdf['res'] == 'WIN'])
        losses = len(tdf[tdf['res'] == 'LOSS'])
        
        total = len(tdf)
        wr = (wins / total) * 100 if total > 0 else 0
        
        avg_pnl = tdf['pnl'].mean()
        total_pnl = tdf['pnl'].sum()
        
        # Max Drawdown in units
        tdf['cum_pnl'] = tdf['pnl'].cumsum()
        running_max = tdf['cum_pnl'].cummax()
        drawdowns = tdf['cum_pnl'] - running_max
        max_dd = drawdowns.min()
        
        print("\n\n" + "="*40)
        print("📈 SOVEREIGN BACKTEST PERFORMANCE")
        print("="*40)
        print(f"Total Trades: {total}")
        print(f"Win Rate:     {wr:.2f}%")
        print(f"Total Alpha:  {total_pnl:.2f} Units")
        print(f"Avg per Trade: {avg_pnl:.2f} Units")
        print(f"Max Drawdown: {max_dd:.2f} Units")
        print("="*40)
        
        # --- Generate Equity Curve ---
        try:
            plt.figure(figsize=(10, 6))
            plt.plot(pd.to_datetime(tdf['ts']), tdf['cum_pnl'], label='Sovereign Alpha (Units)', color='#00FFCC')
            plt.title(f'Sovereign Equity Curve (24/7 Mode) - {self.symbol}')
            plt.xlabel('Date')
            plt.ylabel('Alpha Units (1% Risk)')
            plt.grid(True, alpha=0.3)
            plt.legend()
            plt.savefig('equity_curve.png')
            print(f"🖼️ Equity curve saved to equity_curve.png")
        except Exception as e:
            print(f"Chart gen failed: {e}")

        with open('results_v2.json', 'w') as f:
            json.dump(self.trades, f, indent=2)

if __name__ == "__main__":
    # Full Sovereign Backtest: Year 2025
    bt = SovereignBacktestV2(
        start_date='2025-01-01', 
        end_date='2026-01-01'
    )
    bt.run()
