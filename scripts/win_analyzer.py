import sqlite3
import os
import shutil
import json
from datetime import datetime
import glob

def run_win_analysis():
    print("🔍 Beginning Forensic Analysis of Manual Wins...")
    conn = sqlite3.connect('data/smc_alpha.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM journal WHERE pnl > 0 AND strategy = 'ROGUE' ORDER BY pnl DESC")
    wins = cursor.fetchall()
    
    print(f"Total ROGUE Wins: {len(wins)}")
    
    hour_distribution = {}
    symbols = {}
    total_rogue_pnl = 0
    
    for row in wins:
        d = dict(row)
        total_rogue_pnl += d['pnl']
        symbols[d['symbol']] = symbols.get(d['symbol'], 0) + 1
        
        try:
            ts = datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00'))
            hour = ts.hour
            hour_distribution[hour] = hour_distribution.get(hour, 0) + 1
        except:
            pass
            
    print(f"Total PnL from Manual Wins: ${total_rogue_pnl:,.2f}")
    best_hour = max(hour_distribution, key=hour_distribution.get) if hour_distribution else "Unknown"
    best_symbol = max(symbols, key=symbols.get) if symbols else "Unknown"
    
    print(f"Most Profitable Hour: {best_hour}:00 UTC")
    print(f"Most Profitable Asset: {best_symbol}")
    
    # Extract Charts for Top 3 Wins
    charts_dir = 'data/charts/'
    if not os.path.exists(charts_dir):
        print("No charts directory found.")
        return
        
    all_charts = glob.glob(os.path.join(charts_dir, 'pulse_*.png'))
    chart_timestamps = []
    for c in all_charts:
        try:
            ts = int(c.split('pulse_')[1].split('.png')[0])
            chart_timestamps.append((ts, c))
        except:
            pass
            
    chart_timestamps.sort()
    
    out_dir = '/Users/nicholasmacaskill/.gemini/antigravity/brain/209ec3c4-1b4f-45fe-af3f-e21699908d91/'
    copied = []
    
    print("\n📸 Extracting Top 3 Win Snapshots:")
    for i, row in enumerate(wins[:3]):
        d = dict(row)
        try:
            trade_ts = datetime.fromisoformat(d['timestamp'].replace('Z', '+00:00')).timestamp()
            
            # Find closest chart (must be within 2 hours)
            closest_chart = None
            min_diff = float('inf')
            
            for ts, path in chart_timestamps:
                diff = abs(ts - trade_ts)
                if diff < min_diff and diff < 7200: # 2 hours
                    min_diff = diff
                    closest_chart = path
                    
            if closest_chart:
                out_path = os.path.join(out_dir, f"win_chart_{i+1}.png")
                shutil.copy2(closest_chart, out_path)
                copied.append({
                    "rank": i+1,
                    "pnl": d['pnl'],
                    "symbol": d['symbol'],
                    "image": out_path
                })
                print(f"  [+] Win {i+1}: ${d['pnl']} -> Found {os.path.basename(closest_chart)}")
            else:
                print(f"  [-] Win {i+1}: ${d['pnl']} -> No chart found within 2 hours.")
        except Exception as e:
            print(f"  [!] Error processing win {i+1}: {e}")

    with open(os.path.join(out_dir, 'win_analysis.json'), 'w') as f:
        json.dump({
            "total_rogue_wins": len(wins),
            "total_rogue_pnl": total_rogue_pnl,
            "best_hour": best_hour,
            "best_symbol": best_symbol,
            "top_charts": copied
        }, f)

if __name__ == "__main__":
    run_win_analysis()
