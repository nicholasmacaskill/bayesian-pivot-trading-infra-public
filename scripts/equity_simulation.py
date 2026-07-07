import ccxt
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json

class EquitySimulation:
    def __init__(self, start_equity=100000.0, risk_pct=0.0075):
        self.equity = start_equity
        self.risk_pct = risk_pct
        self.exchange = ccxt.binance({'enableRateLimit': True})
        
    def fetch_data(self):
        print("📥 Fetching 90 days of 5m data...")
        # 90 Days lookback
        start_ts = int((datetime.now() - timedelta(days=90)).timestamp() * 1000)
        
        all_data = []
        current_ts = start_ts
        
        # We need end_ts to act as a loop breaker
        end_ts = int(datetime.now().timestamp() * 1000)

        while current_ts < end_ts:
            try:
                ohlcv = self.exchange.fetch_ohlcv('BTC/USDT', '5m', since=current_ts, limit=1000)
                if not ohlcv: break
                all_data.extend(ohlcv)
                current_ts = ohlcv[-1][0] + 1
            except Exception as e:
                print(f"Error: {e}")
                break
                
        df = pd.DataFrame(all_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df = df.drop_duplicates(subset='timestamp')
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        df['atr'] = np.max(ranges, axis=1).rolling(14).mean()
        
        print(f"✅ Loaded {len(df)} candles")
        return df

    def run_sim_silently(self):
        # Re-using cached data if possible would be better but let's just re-fetch for simplicity or better yet modify run to verify
        # To avoid re-fetching, let's fix the class to cache data
        if not hasattr(self, 'df'):
            self.df = self.fetch_data()
            
            # Pre-calc bias once
            df_4h = self.df.set_index('timestamp').resample('4h').agg({'close': 'last'}).dropna()
            df_4h['ema_20'] = df_4h['close'].ewm(span=20).mean()
            df_4h['ema_50'] = df_4h['close'].ewm(span=50).mean()
            df_4h['bias_val'] = np.where(df_4h['ema_20'] > df_4h['ema_50'], 'BULLISH', 'BEARISH')
            df_merged = pd.merge_asof(self.df, df_4h[['bias_val']], left_on='timestamp', right_index=True, direction='backward')
            self.df['bias'] = df_merged['bias_val'].fillna('NEUTRAL')
            
        equity_curve = [self.equity]
        trades = []
        
        for idx in range(300, len(self.df)-49):
            row = self.df.iloc[idx]
            hour = row['timestamp'].hour
            
            if not (12 <= hour < 20): continue
            if row['bias'] == 'NEUTRAL': continue
            
            if np.random.random() > 0.0125: continue
            
            risk_amt = self.equity * self.risk_pct
            rand = np.random.random()
            
            pnl = 0
            if rand < 0.28: pnl = risk_amt * 2.25
            elif rand < 0.48: pnl = risk_amt * 0.2
            else: pnl = -risk_amt
                
            self.equity += pnl
            equity_curve.append(self.equity)
            trades.append({'pnl': pnl})
            
        return trades, equity_curve

if __name__ == "__main__":
    risk_models = [0.0065]
    
    print("\n" + "="*80)
    print(f"{'RISK PER TRADE':<15} | {'NET PROFIT (90d)':<20} | {'ROI (90d)':<15} | {'ANNUALIZED':<15}")
    print("-" * 80)
            
    for risk in risk_models:
        sim = EquitySimulation(start_equity=100000.0, risk_pct=risk)
        trades, curve = sim.run_sim_silently() 
        
        net_profit = curve[-1] - 100000
        roi = (net_profit / 100000) * 100
        annual = net_profit * 4
        
        print(f"{risk*100:<14}% | ${net_profit:,.2f}          | {roi:.2f}%          | ${annual:,.2f}")
    print("="*80)
