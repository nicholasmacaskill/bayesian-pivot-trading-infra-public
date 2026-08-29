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
            
            # Fetch open positions and compute floating PnL
            open_pos = h.get_open_positions()
            floating_pnl = sum(float(p.get('pnl', 0.0)) for p in open_pos)
            current_equity = balance + floating_pnl
            
            # Determine initial account size tier
            if balance >= 40000.0:
                initial_tier = 50000.0
            elif balance >= 18000.0:
                initial_tier = 25000.0
            else:
                initial_tier = 10000.0
                
            # Upcomers prop drawdown limits (Daily: 4.0% = $400 on $10k, Max Total: 5.0% = $500 on $10k)
            daily_limit_pct = 4.0
            daily_limit_usd = initial_tier * (daily_limit_pct / 100.0)
            
            max_limit_pct = 5.0
            max_limit_usd = initial_tier * (max_limit_pct / 100.0)
            
            total_loss = initial_tier - current_equity
            total_loss_pct = (total_loss / initial_tier) * 100.0
            
            buffer_usd = daily_limit_usd - max(total_loss, 0.0)
            
            print(f"\nAccount {i+1} ({h.email}) - Tier: ${initial_tier:,.0f}")
            print(f"   Balance: ${balance:,.2f} | Floating PnL: ${floating_pnl:,.2f} | Equity: ${current_equity:,.2f}")
            print(f"   Total Cumulative Loss: ${total_loss:,.2f} ({total_loss_pct:.2f}%)")
            print(f"   Daily Limit: ${daily_limit_usd:,.2f} (4%) | Max Limit: ${max_limit_usd:,.2f} (8%)")
            print(f"   Remaining Safe Buffer: ${buffer_usd:,.2f}")
            
            if total_loss_pct >= 3.0:
                print(f"   ⚠️ WARNING: Near daily limit (> 3.0% loss)!")
            else:
                print(f"   ✅ HEALTHY: Safe within parameters.")
                
        except Exception as e:
            print(f"Account {i+1} error: {e}")

if __name__ == "__main__":
    main()
