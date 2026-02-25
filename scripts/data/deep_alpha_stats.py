import json
import pandas as pd
from datetime import datetime

def deep_stats():
    try:
        with open("data/manual_trades_supabase.json", "r") as f:
            data = json.load(f)
    except:
        print("❌ Error: No manual trade data found.")
        return

    df = pd.DataFrame(data)
    df['ts'] = pd.to_datetime(df['timestamp'], format='ISO8601', utc=True)
    import pytz
    est = pytz.timezone('US/Eastern')
    df['ts_est'] = df['ts'].dt.tz_convert(est)
    
    # Basic Metrics
    total = len(df)
    wins = df[df['pnl'] > 0]
    
    win_rate = (len(wins) / total) * 100 if total > 0 else 0
    total_pnl = df['pnl'].sum()
    
    # Profitable Types (Side)
    stats_side = df.groupby('side')['pnl'].agg(['count', 'sum', 'mean']).reset_index()
    stats_side['win_rate'] = df.groupby('side').apply(lambda x: (x['pnl'] > 0).mean() * 100 if len(x)>0 else 0).values

    # Time Clustering (Session)
    df['hour'] = df['ts_est'].dt.hour
    def get_session(h):
        if 2 <= h < 5: return "London Open"
        if 7 <= h < 11: return "NY Morning"
        if 11 <= h < 13: return "NY Lunch"
        if 13 <= h < 16: return "NY Afternoon"
        if 20 <= h <= 24 or 0 <= h < 2: return "Asian"
        return "Other"
    
    df['session'] = df['hour'].apply(get_session)
    stats_session = df.groupby('session')['pnl'].agg(['count', 'sum', 'mean']).reset_index()
    stats_session['win_rate'] = df.groupby('session').apply(lambda x: (x['pnl'] > 0).mean() * 100).values

    print(f"--- 📊 DEEP ALPHA STATS ---")
    print(f"Total Trades: {total}")
    print(f"Overall Win Rate: {win_rate:.2f}%")
    print(f"Total PnL: ${total_pnl:.2f}")
    
    print("\n--- 💸 PROFITABILITY BY SIDE ---")
    print(stats_side.to_string(index=False))
    
    print("\n--- ⏰ PROFITABILITY BY SESSION ---")
    print(stats_session.sort_values(by='sum', ascending=False).to_string(index=False))

    # Top Patterns (mention mentor feedback keywords if possible)
    print("\n--- 🔍 WINNING NARRATIVES (Keywords) ---")
    winning_feedback = " ".join(wins['mentor_feedback'].astype(str))
    keywords = ["Liquidity", "FVG", "MSS", "Order Block", "Sponsorship", "Sweep", "Range"]
    found_keywords = {k: winning_feedback.lower().count(k.lower()) for k in keywords}
    for k, v in sorted(found_keywords.items(), key=lambda x: x[1], reverse=True):
        if v > 0: print(f"   - {k}: referenced {v} times in winning audits")

if __name__ == "__main__":
    deep_stats()
