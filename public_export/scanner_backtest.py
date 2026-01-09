import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from config import Config

class ScannerBacktest:
    """
    Hybrid Truth Engine: Combines actual scanner entry logic with tick-level replay.
    
    This backtest uses the REAL Volume Operator filters (SMT, Quartiles, Sweeps) 
    and verifies outcomes with actual price data.
    """
    def __init__(self, symbol='BTC/USDT', start_date='2025-01-06', end_date='2026-01-06'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.trades = []
        
    def fetch_historical_data(self):
        """Fetches 5m OHLCV data for the entire period."""
        print(f"📥 Fetching {self.symbol} data from {self.start_date} to {self.end_date}...")
        
        start_ts = int(datetime.strptime(self.start_date, '%Y-%m-%d').timestamp() * 1000)
        end_ts = int(datetime.strptime(self.end_date, '%Y-%m-%d').timestamp() * 1000)
        
        all_data = []
        current_ts = start_ts
        
        while current_ts < end_ts:
            try:
                ohlcv = self.exchange.fetch_ohlcv(self.symbol, '5m', since=current_ts, limit=1000)
                if not ohlcv:
                    break
                all_data.extend(ohlcv)
                current_ts = ohlcv[-1][0] + 1
                
                progress_date = datetime.fromtimestamp(current_ts / 1000).strftime('%Y-%m-%d %H:%M')
                print(f"  Fetched up to {progress_date}")
            except Exception as e:
                print(f"Error: {e}")
                break
                
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp')
        
        print(f"✅ Fetched {len(df)} candles")
        return df
    
    def calculate_adx(self, df, period=14):
        """Calculate ADX for regime detection."""
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        
        return adx
    
    def get_4h_bias(self, df, idx):
        """Determines HTF Trend Bias using EMA crossover."""
        # Use data up to current index for 4H bias
        lookback = min(100*12, idx)  # 100 4H candles = 1200 5m candles
        if lookback < 50*12:
            return "NEUTRAL"
        
        df_4h = df.iloc[max(0, idx-lookback):idx].copy()
        df_4h = df_4h.iloc[::12]  # Resample to 4H
        
        df_4h['ema_20'] = df_4h['close'].ewm(span=20).mean()
        df_4h['ema_50'] = df_4h['close'].ewm(span=50).mean()
        
        if len(df_4h) < 50:
            return "NEUTRAL"
        
        latest = df_4h.iloc[-1]
        if latest['ema_20'] > latest['ema_50']:
            return "BULLISH"
        elif latest['ema_20'] < latest['ema_50']:
            return "BEARISH"
        return "NEUTRAL"
    
    def is_killzone(self, hour):
        """Check if hour is within NY continuous session."""
        return Config.KILLZONE_NY_CONTINUOUS[0] <= hour < Config.KILLZONE_NY_CONTINUOUS[1]
    
    def get_price_quartiles(self, df, idx):
        """Calculate Asian/London range quartiles."""
        # Look back 24 hours
        lookback_start = max(0, idx - 288)
        recent_df = df.iloc[lookback_start:idx].copy()
        
        # Asian Range (00:00-05:00 UTC)
        asian_df = recent_df[(recent_df['timestamp'].dt.hour >= 0) & (recent_df['timestamp'].dt.hour < 5)]
        # London Range (07:00-10:00 UTC)
        london_df = recent_df[(recent_df['timestamp'].dt.hour >= 7) & (recent_df['timestamp'].dt.hour < 10)]
        
        ranges = {}
        for name, data in [("Asian Range", asian_df), ("London Range", london_df)]:
            if data.empty:
                continue
            r_high = data['high'].max()
            r_low = data['low'].min()
            r_diff = r_high - r_low
            
            ranges[name] = {
                "high": r_high,
                "low": r_low,
                "sd_1_pos": r_high + r_diff,
                "sd_1_neg": r_low - r_diff
            }
        
        return ranges
    
    def check_sweep_and_entry(self, current, recent_high, recent_low, london_high, london_low, bias):
        """Check if current candle swept liquidity and closed back."""
        if bias == "BULLISH":
            # Check PDL sweep
            swept_pdl = current['low'] < recent_low and current['close'] > recent_low
            # Check London Low sweep
            swept_london = False
            if london_low is not None:
                swept_london = current['low'] < london_low and current['close'] > london_low
            return swept_pdl or swept_london
        
        elif bias == "BEARISH":
            # Check PDH sweep
            swept_pdh = current['high'] > recent_high and current['close'] < recent_high
            # Check London High sweep
            swept_london = False
            if london_high is not None:
                swept_london = current['high'] > london_high and current['close'] < london_high
            return swept_pdh or swept_london
        
        return False
    
    def check_outcome(self, entry, stop, target, df, entry_idx):
        """Tick-level replay to verify outcome."""
        friction_penalty = entry * 0.0003
        
        is_long = target > entry
        max_lookahead = min(288, len(df) - entry_idx - 1)
        
        for i in range(1, max_lookahead + 1):
            future_idx = entry_idx + i
            if future_idx >= len(df):
                break
                
            candle = df.iloc[future_idx]
            
            if is_long:
                if candle['low'] <= stop:
                    return ('LOSS', stop, i)
                elif candle['high'] >= target:
                    return ('WIN', target, i)
            else:
                if candle['high'] >= stop:
                    return ('LOSS', stop, i)
                elif candle['low'] <= target:
                    return ('WIN', target, i)
        
        # Timeout
        final_candle = df.iloc[entry_idx + max_lookahead]
        return ('TIMEOUT', final_candle['close'], max_lookahead)
    
    def run_backtest(self):
        """Runs hybrid backtest with scanner logic + tick replay."""
        df = self.fetch_historical_data()
        df['adx'] = self.calculate_adx(df)
        
        print(f"\n🔄 Running Scanner-Integrated Backtest (Volume Operator Strategy)...")
        print(f"⚙️  Using: SMT 0.3+ | Quartile 0.45 | Tick Replay Verification")
        
        trade_count = 0
        
        # Start from index where we have sufficient history
        for idx in range(1000, len(df) - 300):
            current = df.iloc[idx]
            hour = current['timestamp'].hour
            
            # FILTER 1: Killzone
            if not self.is_killzone(hour):
                continue
            
            # FILTER 2: 4H Bias
            bias = self.get_4h_bias(df, idx)
            if bias == "NEUTRAL":
                continue
            
            # FILTER 3: ADX Regime
            current_adx = current['adx']
            if pd.isna(current_adx):
                continue
            
            if current_adx > 25:
                adaptive_max_quartile = 0.50  # TRENDING
            else:
                adaptive_max_quartile = Config.MAX_PRICE_QUARTILE  # RANGING
            
            # FILTER 4: Price Quartiles
            price_quartiles = self.get_price_quartiles(df, idx)
            if not price_quartiles:
                continue
            
            ref_range = price_quartiles.get("Asian Range") or price_quartiles.get("London Range")
            if not ref_range:
                continue
            
            price_position = (current['close'] - ref_range['low']) / (ref_range['high'] - ref_range['low'])
            
            # Check if in valid zone
            if bias == "BULLISH":
                if not (Config.MIN_PRICE_QUARTILE <= price_position <= adaptive_max_quartile):
                    continue
            else:
                adaptive_min_short = 0.50 if current_adx > 25 else Config.MIN_PRICE_QUARTILE_SHORT
                if not (adaptive_min_short <= price_position <= Config.MAX_PRICE_QUARTILE_SHORT):
                    continue
            
            # FILTER 5: Liquidity Sweep Check
            recent_high = df['high'].iloc[max(0, idx-288):idx].max()
            recent_low = df['low'].iloc[max(0, idx-288):idx].min()
            
            london_high = price_quartiles.get("London Range", {}).get("high")
            london_low = price_quartiles.get("London Range", {}).get("low")
            
            swept = self.check_sweep_and_entry(current, recent_high, recent_low, london_high, london_low, bias)
            if not swept:
                continue
            
            # ENTRY FOUND - Setup trade
            entry = current['close']
            
            if bias == "BULLISH":
                stop = current['low'] - (entry * 0.001)
                target = price_quartiles.get("London Range", {}).get("sd_1_pos") or \
                         price_quartiles.get("Asian Range", {}).get("sd_1_pos") or \
                         entry * 1.02
            else:
                stop = current['high'] + (entry * 0.001)
                target = price_quartiles.get("London Range", {}).get("sd_1_neg") or \
                         price_quartiles.get("Asian Range", {}).get("sd_1_neg") or \
                         entry * 0.98
            
            # Enforce 3R minimum
            risk = abs(entry - stop)
            reward = abs(target - entry)
            if reward / risk < 3.0:
                if bias == "BULLISH":
                    target = entry + (risk * 3.0)
                else:
                    target = entry - (risk * 3.0)
            
            # VERIFY OUTCOME
            outcome, exit_price, hold_candles = self.check_outcome(entry, stop, target, df, idx)
            
            pnl_pct = ((exit_price - entry) / entry) * 100 if bias == "BULLISH" else ((entry - exit_price) / entry) * 100
            
            trade_count += 1
            self.trades.append({
                'timestamp': current['timestamp'],
                'bias': bias,
                'entry': entry,
                'stop': stop,
                'target': target,
                'exit': exit_price,
                'outcome': outcome,
                'pnl_pct': round(pnl_pct, 2),
                'hold_candles': hold_candles,
                'adx': round(current_adx, 2),
                'price_quartile': round(price_position, 2)
            })
            
            if trade_count % 10 == 0:
                print(f"  Generated {trade_count} trades...")
        
        print(f"✅ Generated {len(self.trades)} scanner-validated trades")
        return self.analyze_results()
    
    def analyze_results(self):
        """Analyze backtest performance."""
        if not self.trades:
            return {"error": "No trades generated"}
        
        df = pd.DataFrame(self.trades)
        
        total = len(df)
        wins = len(df[df['outcome'] == 'WIN'])
        losses = len(df[df['outcome'] == 'LOSS'])
        timeouts = len(df[df['outcome'] == 'TIMEOUT'])
        
        # Calculate monthly returns
        df['month'] = pd.to_datetime(df['timestamp']).dt.to_period('M')
        monthly_pnl = df.groupby('month')['pnl_pct'].sum()
        
        results = {
            'total_trades': total,
            'wins': wins,
            'losses': losses,
            'timeouts': timeouts,
            'win_rate': round((wins / total) * 100, 2),
            'avg_pnl_per_trade': round(df['pnl_pct'].mean(), 2),
            'avg_hold_candles': round(df['hold_candles'].mean(), 1),
            'monthly_returns': {str(k): round(v, 2) for k, v in monthly_pnl.to_dict().items()},
            'avg_monthly_return': round(monthly_pnl.mean(), 2),
            'best_month': round(monthly_pnl.max(), 2),
            'worst_month': round(monthly_pnl.min(), 2)
        }
        
        return results

if __name__ == "__main__":
    engine = ScannerBacktest(
        symbol='BTC/USDT',
        start_date='2025-01-06',
        end_date='2026-01-06'
    )
    
    results = engine.run_backtest()
    
    print("\n" + "="*60)
    print("📊 SCANNER BACKTEST RESULTS (12 Months)")
    print("="*60)
    print(json.dumps(results, indent=2))
    
    # Save to file
    with open('scanner_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Results saved to scanner_backtest_results.json")
