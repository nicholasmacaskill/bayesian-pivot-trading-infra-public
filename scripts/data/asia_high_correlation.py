import json
import pandas as pd
import ccxt
from datetime import datetime, timedelta
import pytz

def check_asia_high_correlation():
    print("🔭 Correlating Asian Wins with Session Highs...")
    
    try:
        with open("data/manual_trades_supabase.json", "r") as f:
            data = json.load(f)
    except:
        return

    df = pd.DataFrame(data)
    df['ts_utc'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
    
    # Session Logic (EST)
    est = pytz.timezone('US/Eastern')
    utc = pytz.utc
    df['ts_est'] = df['ts_utc'].dt.tz_convert(est)
    df['hour_est'] = df['ts_est'].dt.hour
    
    # Filter for Asian Session (8 PM - 2 AM EST)
    def is_asia(h):
        return (h >= 20) or (h < 2)
    
    asia_trades = df[df['hour_est'].apply(is_asia)]
    
    exchange = ccxt.binance()
    results = []
    
    for _, trade in asia_trades.iterrows():
        trade_ts_utc = trade['ts_utc']
        trade_ts_est = trade_ts_utc.astimezone(est)
        
        # Asian session starts at 8 PM (20:00) EST.
        # Check everything leading up to the entry
        asia_start_est = est.localize(datetime.combine(trade_ts_est.date() - timedelta(days=1 if trade_ts_est.hour < 20 else 0), datetime.min.time()).replace(hour=20))
        asia_end_est = trade_ts_est 
        
        since = int(asia_start_est.astimezone(utc).timestamp() * 1000)
        
        try:
            candles = exchange.fetch_ohlcv('BTC/USDT', '5m', since=since, limit=100)
            asia_df = pd.DataFrame(candles, columns=['ts', 'o', 'h', 'l', 'c', 'v'])
            asia_df['dt_utc'] = pd.to_datetime(asia_df['ts'], unit='ms', utc=True)
            asia_df['dt_est'] = asia_df['dt_utc'].dt.tz_convert(est)
            
            mask = (asia_df['dt_est'] >= asia_start_est) & (asia_df['dt_est'] < asia_end_est)
            asia_range = asia_df[mask]
            
            if asia_range.empty:
                continue
                
            asia_high = asia_range['h'].max()
            asia_low = asia_range['l'].min()
            asia_mid = (asia_high + asia_low) / 2
            
            entry_price = float(trade['price'])
            
            pos = "ABOVE HIGH" if entry_price >= (asia_high * 0.9998) else \
                  "BELOW LOW" if entry_price <= (asia_low * 1.0002) else \
                  "INSIDE (UPPER)" if entry_price > asia_mid else "INSIDE (LOWER)"
            
            results.append({
                "id": trade['trade_id'],
                "pnl": trade['pnl'],
                "entry": entry_price,
                "asia_high": asia_high,
                "asia_low": asia_low,
                "pos": pos,
                "date": trade_ts_est.date()
            })
            print(f"   - {trade_ts_est.strftime('%H:%M')} | Entry: {entry_price:.0f} | Asia [H:{asia_high:.0f} L:{asia_low:.0f}] | {pos} | PnL: ${trade['pnl']}")
            
        except Exception as e:
            print(f"   ⚠️ Error: {e}")

    results_df = pd.DataFrame(results)
    if not results_df.empty:
        print(f"\n📈 ASIAN POSITION STATS:")
        print(results_df.groupby('pos')['pnl'].agg(['count', 'sum']).reset_index().to_string(index=False))

if __name__ == "__main__":
    check_asia_high_correlation()
