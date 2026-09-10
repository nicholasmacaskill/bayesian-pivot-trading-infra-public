import sys
import os
sys.path.append(os.getcwd())

from datetime import datetime, timezone
from src.clients.tl_client import TradeLockerClient

def main():
    tl = TradeLockerClient()
    print("=== PROP GUARDIAN: FLEET DRAWDOWN AUDIT ===")

    for i, h in enumerate(tl.helpers):
        try:
            h.login()
            # Fetch all account details
            details_ok = h.get_account_details()
            balance = getattr(h, 'balance', 0.0)
            
            # Determine initial account size tier
            if balance >= 40000.0:
                initial_tier = 50000.0
            elif balance >= 18000.0:
                initial_tier = 25000.0
            else:
                initial_tier = 10000.0

            # Fetch open positions and compute floating PnL
            open_pos = h.get_open_positions()
            floating_pnl = sum(float(p.get('pnl', 0.0)) for p in open_pos)
            current_equity = balance + floating_pnl
            
            trades = h.get_recent_history(hours=336) # 14 days
            
            # Compute historical Peak High Water Mark (HWM)
            pnl_sum = sum(float(t.get('pnl', 0.0)) for t in trades)
            start_of_window = balance - pnl_sum
            running = start_of_window
            peak = max(balance, initial_tier)
            for t in trades:
                running += float(t.get('pnl', 0.0))
                if running > peak:
                    peak = running
            peak_hwm = max(peak, balance)
            
            # Upcomers 5% Trailing Max Drawdown Floor = HWM - 5% of Initial Tier
            max_limit_usd = initial_tier * 0.05
            daily_limit_usd = initial_tier * 0.04
            
            trailing_floor = peak_hwm - max_limit_usd
            remaining_trailing_buffer = current_equity - trailing_floor
            
            print(f"\nAccount {i+1} ({h.email}) - Tier: ${initial_tier:,.0f}")
            print(f"   Balance: ${balance:,.2f} | Floating PnL: ${floating_pnl:,.2f} | Equity: ${current_equity:,.2f}")
            print(f"   Peak High Water Mark (HWM): ${peak_hwm:,.2f} (+${peak_hwm - initial_tier:,.2f} peak gain)")
            print(f"   Hard Trailing Floor (5% below HWM): ${trailing_floor:,.2f}")
            print(f"   Remaining Trailing Buffer: ${remaining_trailing_buffer:,.2f}")
            print(f"   Daily Limit: ${daily_limit_usd:,.2f} (4%) | Max 5% Limit: ${max_limit_usd:,.2f}")
            
            if remaining_trailing_buffer <= (initial_tier * 0.02):
                print(f"   ⚠️ WARNING: Tight Buffer (< 2% to Trailing Floor)!")
            else:
                print(f"   ✅ HEALTHY: Safe within parameters.")
                
        except Exception as e:
            print(f"Account {i+1} error: {e}")

if __name__ == "__main__":
    main()
