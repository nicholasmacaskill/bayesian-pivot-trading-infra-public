import json
import pandas as pd
from datetime import datetime, timedelta

def delta_analysis():
    print("📉 Starting Delta Analysis (Human Alpha vs Bot Scanner)...")
    
    try:
        with open("data/manual_trades_supabase.json", "r") as f:
            manual_trades = json.load(f)
        with open("data/bot_scans_supabase.json", "r") as f:
            bot_scans = json.load(f)
    except FileNotFoundError:
        print("❌ Error: Data files not found. Run extraction first.")
        return

    # Convert to DataFrames
    df_manual = pd.DataFrame(manual_trades)
    df_scans = pd.DataFrame(bot_scans)
    
    # Convert timestamps
    df_manual['ts'] = pd.to_datetime(df_manual['timestamp'], format='ISO8601')
    df_scans['ts'] = pd.to_datetime(df_scans['timestamp'], format='ISO8601')
    
    results = {
        "total_manual_trades": len(df_manual),
        "total_bot_scans": len(df_scans),
        "divergent_trades": [], # Manual trades with NO bot scan nearby
        "congruent_trades": []  # Manual trades where bot also saw something
    }
    
    # Matching Window (e.g. 30 mins)
    WINDOW = timedelta(minutes=30)
    
    for _, trade in df_manual.iterrows():
        # Find scans for same symbol within WINDOW
        mask = (df_scans['symbol'] == trade['symbol']) & \
               (df_scans['ts'] >= trade['ts'] - WINDOW) & \
               (df_scans['ts'] <= trade['ts'] + WINDOW)
        
        nearby_scans = df_scans[mask]
        
        trade_summary = {
            "trade_id": trade['trade_id'],
            "symbol": trade['symbol'],
            "side": trade['side'],
            "pnl": trade['pnl'],
            "ts": trade['timestamp'],
            "ai_grade": trade['ai_grade'],
            "mentor_feedback": trade['mentor_feedback'],
            "matching_scans": []
        }
        
        if not nearby_scans.empty:
            for _, scan in nearby_scans.iterrows():
                trade_summary['matching_scans'].append({
                    "pattern": scan['pattern'],
                    "bias": scan['bias'],
                    "ai_score": scan['ai_score'],
                    "ts": scan['timestamp']
                })
            results['congruent_trades'].append(trade_summary)
        else:
            results['divergent_trades'].append(trade_summary)
            
    # Statistics
    print(f"   ✅ Analyzed {len(df_manual)} manual trades.")
    print(f"   🤖 Congruent (Bot also saw it): {len(results['congruent_trades'])}")
    print(f"   👤 Divergent (Human Only): {len(results['divergent_trades'])}")
    
    # Save delta report
    with open("data/delta_analysis_report.json", "w") as f:
        json.dump(results, f, indent=4)
    print("   📊 Saved analysis to data/delta_analysis_report.json")
    
    # Print Human Alpha Highlights
    print("\n--- 🌟 HUMAN ALPHA HIGHLIGHTS (Divergent Wins) ---")
    divergent_wins = [t for t in results['divergent_trades'] if t['pnl'] > 0]
    divergent_wins.sort(key=lambda x: x['pnl'], reverse=True)
    
    for t in divergent_wins[:5]:
        print(f"   - {t['symbol']} {t['side']} | PnL: ${t['pnl']:.2f} | Time: {t['ts']}")
        print(f"     Mentor feedback: {t['mentor_feedback'][:150]}...")
        print("-" * 40)

if __name__ == "__main__":
    delta_analysis()
