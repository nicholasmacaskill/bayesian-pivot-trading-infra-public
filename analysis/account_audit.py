import os
import sys
from datetime import datetime, timezone

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from dotenv import load_dotenv

def audit_drawdown():
    print("📊 Performing Real-Time Drawdown Audit...")
    load_dotenv(".env")
    load_dotenv(".env.local")
    tl = TradeLockerClient()
    
    total_equity = 0.0
    total_today_pnl = 0.0
    total_open_pnl = 0.0
    
    for i, helper in enumerate(tl.helpers):
        print(f"\n--- Account {i+1} ({helper.email}) ---")
        if not helper.access_token:
            if not helper.login():
                print("   ❌ Login Failed")
                continue
        
        # 1. Equity
        equity = helper.get_equity()
        total_equity += equity
        print(f"   Current Equity: ${equity:,.2f}")
        
        # 2. Open Positions
        positions = helper.get_open_positions()
        open_pnl = sum(p['pnl'] for p in positions)
        total_open_pnl += open_pnl
        print(f"   Open PnL: ${open_pnl:,.2f}")
        for p in positions:
            print(f"      - {p['symbol']} {p['side']} PnL: ${p['pnl']:.2f}")
            
        # 3. Today's History
        # We'll fetch 24h of history and filter for trades closed after 00:00 UTC today
        now_utc = datetime.now(timezone.utc)
        start_of_day = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        
        history = helper.get_recent_history(hours=24)
        today_closed_pnl = 0.0
        for t in history:
            # Note: close_time might need parsing depending on TL format
            try:
                # Basic ISO parsing or timestamp
                close_time = datetime.fromisoformat(t['close_time'].replace('Z', '+00:00'))
                if close_time >= start_of_day:
                    today_closed_pnl += t['pnl']
            except:
                # If parsing fails, we assume it's recent enough for this audit if fetched via hours=24
                # but let's be safe and try to parse it.
                continue
                
        total_today_pnl += today_closed_pnl
        print(f"   Today's Closed PnL: ${today_closed_pnl:,.2f}")
        
        # 4. Starting Balance Calculation
        current_balance = equity - open_pnl
        start_of_day_balance = current_balance - today_closed_pnl
        print(f"   Start-of-Day Balance: ${start_of_day_balance:,.2f}")
        
        # 5. Daily Drawdown
        daily_drawdown_dollars = start_of_day_balance - equity
        daily_drawdown_pct = (daily_drawdown_dollars / start_of_day_balance) * 100 if start_of_day_balance > 0 else 0
        
        print(f"   Daily Drawdown: ${daily_drawdown_dollars:,.2f} ({daily_drawdown_pct:.2f}%)")
        
        # Sustainability check (Assuming 4% daily limit standard)
        limit_pct = 4.0
        room_dollars = (start_of_day_balance * (limit_pct/100)) - daily_drawdown_dollars
        print(f"   Room before 5% Limit: ${room_dollars:,.2f}")

    print("\n" + "="*40)
    print(f"AGGREGATED TOTAL EQUITY: ${total_equity:,.2f}")
    print(f"AGGREGATED OPEN PNL: ${total_open_pnl:,.2f}")

if __name__ == "__main__":
    audit_drawdown()
