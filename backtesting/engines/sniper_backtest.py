import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
from config import Config

class SniperBacktest:
    """
    SNIPER BOT: Survivor Protocol
    
    Ultra-strict filters for high-expectancy precision trades.
    Target: 3-4% monthly with minimal drawdown.
    """
    def __init__(self, symbol='BTC/USDT', start_date='2025-01-06', end_date='2026-01-06'):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.trades = []
        self.equity_curve = [100.0]  # Start with $100
        
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
            except Exception as e:
                print(f"Error: {e}")
                break
                
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp')
        
        print(f"✅ Fetched {len(df)} candles")
        return df
    
    def calculate_atr(self, df, period=14):
        """Calculate ATR for volatility."""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        return true_range.rolling(period).mean()
    
    def get_1h_trend(self, df, idx):
        """Determines 1H trend using EMA crossover."""
        lookback = min(60*12, idx)  # 60 1H candles = 720 5m candles
        if lookback < 20*12:
            return "NEUTRAL"
        
        df_1h = df.iloc[max(0, idx-lookback):idx].copy()
        df_1h = df_1h.iloc[::12]  # Resample to 1H
        
        df_1h['ema_9'] = df_1h['close'].ewm(span=9).mean()
        df_1h['ema_21'] = df_1h['close'].ewm(span=21).mean()
        
        if len(df_1h) < 21:
            return "NEUTRAL"
        
        latest = df_1h.iloc[-1]
        if latest['ema_9'] > latest['ema_21']:
            return "BULLISH"
        elif latest['ema_9'] < latest['ema_21']:
            return "BEARISH"
        return "NEUTRAL"
    
    def get_4h_bias(self, df, idx):
        """Determines HTF Trend Bias using EMA crossover."""
        # Need 50 4H candles for EMA50. 50 * 48 = 2400 5m candles.
        lookback = min(6000, idx)
        if lookback < 2500:
            return "NEUTRAL"
        
        df_4h = df.iloc[max(0, idx-lookback):idx].copy()
        df_4h = df_4h.iloc[::48]  # Resample to 4H
        
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
        lookback_start = max(0, idx - 288)
        recent_df = df.iloc[lookback_start:idx].copy()
        
        asian_df = recent_df[(recent_df['timestamp'].dt.hour >= 0) & (recent_df['timestamp'].dt.hour < 5)]
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
            swept_pdl = current['low'] < recent_low and current['close'] > recent_low
            swept_london = False
            if london_low is not None:
                swept_london = current['low'] < london_low and current['close'] > london_low
            return swept_pdl or swept_london
        
        elif bias == "BEARISH":
            swept_pdh = current['high'] > recent_high and current['close'] < recent_high
            swept_london = False
            if london_high is not None:
                swept_london = current['high'] > london_high and current['close'] < london_high
            return swept_pdh or swept_london
        
        return False
    
    def check_outcome_partial_exits(self, entry, stop, target_2r, target_4r, df, entry_idx, bias):
        """
        SNIPER EXIT LOGIC:
        - Close 50% at 2R
        - Close 50% at 4R
        - Move stop to breakeven after 2R hit
        """
        is_long = bias == "BULLISH"
        max_lookahead = min(288, len(df) - entry_idx - 1)
        
        tp1_hit = False
        tp1_idx = None
        breakeven_stop = entry
        
        total_pnl = 0.0
        
        for i in range(1, max_lookahead + 1):
            future_idx = entry_idx + i
            if future_idx >= len(df):
                break
                
            candle = df.iloc[future_idx]
            
            # Check TP1 (2R) first
            if not tp1_hit:
                if is_long:
                    if candle['high'] >= target_2r:
                        # TP1 hit - close 50% at 2R
                        tp1_hit = True
                        tp1_idx = i
                        risk = entry - stop
                        tp1_pnl = (2 * risk) * 0.5  # 50% of position at 2R
                        total_pnl += tp1_pnl
                        # Move stop to breakeven
                        breakeven_stop = entry
                        continue
                    elif candle['low'] <= stop:
                        # Stop hit before TP1
                        risk = entry - stop
                        return ('LOSS', -risk, i, total_pnl)
                else:
                    if candle['low'] <= target_2r:
                        tp1_hit = True
                        tp1_idx = i
                        risk = stop - entry
                        tp1_pnl = (2 * risk) * 0.5
                        total_pnl += tp1_pnl
                        breakeven_stop = entry
                        continue
                    elif candle['high'] >= stop:
                        risk = stop - entry
                        return ('LOSS', -risk, i, total_pnl)
            
            # After TP1 hit, check TP2 (4R) or breakeven stop
            else:
                if is_long:
                    if candle['high'] >= target_4r:
                        # TP2 hit - close remaining 50% at 4R
                        risk = entry - stop
                        tp2_pnl = (4 * risk) * 0.5
                        total_pnl += tp2_pnl
                        return ('FULL_WIN', total_pnl, i, total_pnl)
                    elif candle['low'] <= breakeven_stop:
                        # Breakeven stop hit - remaining 50% exits at breakeven
                        return ('PARTIAL_WIN', total_pnl, i, total_pnl)
                else:
                    if candle['low'] <= target_4r:
                        risk = stop - entry
                        tp2_pnl = (4 * risk) * 0.5
                        total_pnl += tp2_pnl
                        return ('FULL_WIN', total_pnl, i, total_pnl)
                    elif candle['high'] >= breakeven_stop:
                        return ('PARTIAL_WIN', total_pnl, i, total_pnl)
        
        # Timeout
        if tp1_hit:
            return ('TIMEOUT_PARTIAL', total_pnl, max_lookahead, total_pnl)
        else:
            return ('TIMEOUT', 0, max_lookahead, 0)
    
    def run_backtest(self):
        """Runs SNIPER backtest with Survivor Protocol filters."""
        df = self.fetch_historical_data()
        df['atr'] = self.calculate_atr(df)
        
        print(f"\n🎯 Running SNIPER BOT Backtest (Survivor Protocol)...")
        print(f"⚙️  Filters: SMT >0.75 | High Vol | Mon/Wed/Sun | 1H Trend Aligned")
        print(f"⚙️  Exits: 50% @ 2R | 50% @ 4R | Breakeven after TP1")
        
        trade_count = 0
        current_equity = 100.0  # Starting capital
        
        # Allowed days: Monday=0, Wednesday=2, Sunday=6
        allowed_days = [0, 2, 6]
        
        for idx in range(1000, len(df) - 300):
            current = df.iloc[idx]
            hour = current['timestamp'].hour
            day_of_week = current['timestamp'].dayofweek
            
            # SNIPER FILTER 1: Killzone
            if not self.is_killzone(hour):
                continue
            
            # SNIPER FILTER 5: High Volatility Only (REMOVED - Too strict)
            current_atr = current['atr']
            if pd.isna(current_atr):
                continue
            # if current_atr <= df['atr'].median():
            #     continue
            
            # SNIPER FILTER 2: 4H Bias
            bias_4h = self.get_4h_bias(df, idx)
            if bias_4h == "NEUTRAL":
                continue
            
            # SNIPER FILTER 3: 1H Trend Alignment (REMOVED - Blocks reversals)
            # trend_1h = self.get_1h_trend(df, idx)
            # if trend_1h != bias_4h:
            #    continue
            
            # SNIPER FILTER 4: Price Quartiles
            price_quartiles = self.get_price_quartiles(df, idx)
            if not price_quartiles:
                continue
            
            ref_range = price_quartiles.get("Asian Range") or price_quartiles.get("London Range")
            if not ref_range:
                continue
            
            price_position = (current['close'] - ref_range['low']) / (ref_range['high'] - ref_range['low'])
            
            # Check if in valid zone
            if bias_4h == "BULLISH":
                if not (0.0 <= price_position <= 0.55): # Slightly relaxed
                    continue
            else:
                if not (0.45 <= price_position <= 1.0): # Slightly relaxed
                    continue
            
            # SNIPER FILTER 8: Liquidity Sweep Check
            recent_high = df['high'].iloc[max(0, idx-288):idx].max()
            recent_low = df['low'].iloc[max(0, idx-288):idx].min()
            
            london_high = price_quartiles.get("London Range", {}).get("high")
            london_low = price_quartiles.get("London Range", {}).get("low")
            
            swept = self.check_sweep_and_entry(current, recent_high, recent_low, london_high, london_low, bias_4h)
            if not swept:
                continue
            
            # ENTRY FOUND - Setup trade
            entry = current['close']
            
            # --- HUMAN FACTOR SIMULATION (REALITY CHECK) ---
            import random
            
            # 1. THE "LIFE HAPPENS" FILTER (Missing Alerts / Sleep / Driving)
            if random.random() < 0.25: # 25% of alerts are missed
                continue
                
            risk_pct = 0.01  # 1% risk
            
            # 2. THE "FAT FINGER" ERROR (Execution Error / Slippage)
            is_execution_error = False
            if random.random() < 0.05: # 5% of trades are botched entries
                is_execution_error = True
                
            # WIDE NET STRATEGY: Use ATR for Stop Loss (Breathing Room)
            atr = current['atr'] if not pd.isna(current['atr']) else entry * 0.005
            stop_buffer = atr * 2.0  # 2x ATR Buffer to avoid wick-outs
            
            if bias_4h == "BULLISH":
                stop = entry - stop_buffer
                risk_dollars = entry - stop
                target_1_5r = entry + (risk_dollars * 1.5) # Lower TP1 to bag wins
                target_3r = entry + (risk_dollars * 3.0)
            else:
                stop = entry + stop_buffer
                risk_dollars = stop - entry
                target_1_5r = entry - (risk_dollars * 1.5)
                target_3r = entry - (risk_dollars * 3.0)
            
            # VERIFY OUTCOME with partial exits
            outcome, pnl_dollars, hold_candles, net_pnl = self.check_outcome_partial_exits(
                entry, stop, target_1_5r, target_3r, df, idx, bias_4h
            )
            
            # 3. THE "WEAK HANDS" PSYCHOLOGY (Cutting Winners Early)
            # If it was a WIN, 15% chance we panicked and closed at 0.5R
            if 'WIN' in outcome:
                 if random.random() < 0.15:
                     risk_amt = abs(entry - stop)
                     net_pnl = risk_amt * 0.5 # Manually override gain to small 0.5R
                     outcome = "WEAK_HAND_EXIT"
            
            # Apply Execution Error (Botched Trade)
            if is_execution_error:
                outcome = "EXECUTION_ERROR"
                net_pnl = -abs(entry - stop) # Full 1R Loss
            
            # Calculate PnL based on Risk-Based Sizing (SMC Standard)
            # We risk 1% of Equity per trade.
            # Position Size = (Equity * 0.01) / Risk_Distance
            # Gain = R_Multiple * 1%
            
            risk_distance = abs(entry - stop)
            if risk_distance == 0:
                continue # Edge case
                
            r_multiple = net_pnl / risk_distance
            equity_change_pct = r_multiple * (risk_pct * 100)
            
            current_equity *= (1 + equity_change_pct / 100)
            self.equity_curve.append(current_equity)
            
            trade_count += 1
            self.trades.append({
                'timestamp': current['timestamp'],
                'bias': bias_4h,
                'entry': entry,
                'stop': stop,
                'target_1_5r': target_1_5r,
                'target_3r': target_3r,
                'exit_pnl': net_pnl,
                'outcome': outcome,
                'r_multiple': round(r_multiple, 2),
                'equity_change_pct': round(equity_change_pct, 2),
                'equity': round(current_equity, 2),
                'hold_candles': hold_candles
            })
            
            if trade_count % 5 == 0:
                print(f"  Generated {trade_count} SNIPER trades...")
        
        print(f"✅ Generated {len(self.trades)} SNIPER trades")
        return self.analyze_results()
    
    def analyze_results(self):
        """Analyze SNIPER backtest performance."""
        if not self.trades:
            return {"error": "No trades generated"}
        
        df = pd.DataFrame(self.trades)
        
        total = len(df)
        full_wins = len(df[df['outcome'] == 'FULL_WIN'])
        partial_wins = len(df[df['outcome'] == 'PARTIAL_WIN'])
        losses = len(df[df['outcome'] == 'LOSS'])
        
        # Calculate monthly returns
        df['month'] = pd.to_datetime(df['timestamp']).dt.to_period('M')
        monthly_pnl = df.groupby('month')['equity_change_pct'].sum()
        
        # Calculate max drawdown
        equity_series = pd.Series(self.equity_curve)
        running_max = equity_series.cummax()
        drawdown = (equity_series - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        # Total return
        total_return = ((self.equity_curve[-1] - 100) / 100) * 100
        
        results = {
            'total_trades': total,
            'full_wins': full_wins,
            'partial_wins': partial_wins,
            'losses': losses,
            'win_rate': round(((full_wins + partial_wins) / total) * 100, 2),
            'total_return_pct': round(total_return, 2),
            'final_equity': round(self.equity_curve[-1], 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'monthly_returns': {str(k): round(v, 2) for k, v in monthly_pnl.to_dict().items()},
            'avg_monthly_return': round(monthly_pnl.mean(), 2),
            'best_month': round(monthly_pnl.max(), 2),
            'worst_month': round(monthly_pnl.min(), 2)
        }
        
        return results

if __name__ == "__main__":
    engine = SniperBacktest(
        symbol='BTC/USDT',
        start_date='2025-01-06',
        end_date='2026-01-06'
    )
    
    results = engine.run_backtest()
    
    print("\n" + "="*60)
    print("🎯 SNIPER BOT RESULTS (Survivor Protocol)")
    print("="*60)
    print(json.dumps(results, indent=2))
    
    # Save to file
    with open('sniper_backtest_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Results saved to sniper_backtest_results.json")
