import json
import pandas as pd

def session_qualitative_analysis():
    try:
        with open("data/manual_trades_supabase.json", "r") as f:
            data = json.load(f)
    except:
        return

    df = pd.DataFrame(data)
    df['ts'] = pd.to_datetime(df['timestamp'], format='ISO8601')
    df['hour'] = df['ts'].dt.hour
    
    def get_session(h):
        if 2 <= h < 5: return "London"
        if 7 <= h < 16: return "NY"
        return "Other"
    
    df['session'] = df['hour'].apply(get_session)
    
    print("--- 🧠 QUALITATIVE SESSION GAP ---")
    
    london_wins = df[(df['session'] == "London") & (df['pnl'] > 0)]
    ny_losses = df[(df['session'] == "NY") & (df['pnl'] <= 0)]
    
    print(f"\n📍 LONDON EDGE ({len(london_wins)} wins):")
    for _, row in london_wins.head(3).iterrows():
        print(f"- {row['symbol']} {row['side']} | PnL: ${row['pnl']} | Mentor: {row['mentor_feedback'][:120]}...")

    print(f"\n📍 NY FRICTION ({len(ny_losses)} losses):")
    for _, row in ny_losses.head(3).iterrows():
        print(f"- {row['symbol']} {row['side']} | PnL: ${row['pnl']} | Mentor: {row['mentor_feedback'][:120]}...")

if __name__ == "__main__":
    session_qualitative_analysis()
