import sys
import os
import time
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.clients.telegram_notifier import TelegramNotifier

def monitor_sweep():
    load_dotenv('.env.local')
    scanner = SMCScanner()
    notifier = TelegramNotifier()
    symbol = "BTC/USD"
    
    target_upper = 61499.41  # Asian High (BSL)
    target_lower = 60692.00  # London Low (SSL)
    
    print(f"🎯 Sovereign Watcher: Monitoring for Dual Sweeps...", flush=True)
    print(f"📈 Upper Target (Short Setup): >= ${target_upper:,.2f}", flush=True)
    print(f"📉 Lower Target (Long/Invalidation): <= ${target_lower:,.2f}", flush=True)
    print("-" * 50, flush=True)

    try:
        while True:
            df = scanner.fetch_data(symbol, "1m", limit=5)
            if df is not None:
                current_price = df.iloc[-1]['close']
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                trigger_type = None
                target_hit = None
                
                if current_price >= target_upper:
                    trigger_type = "UPPER"
                    target_hit = target_upper
                elif current_price <= target_lower:
                    trigger_type = "LOWER"
                    target_hit = target_lower
                
                if trigger_type:
                    direction = "Asian High (Short Trap)" if trigger_type == "UPPER" else "London Low (Liquidity Grab)"
                    print(f"\n🔔 [{trigger_type} TRIGGERED] {timestamp} | BTC at ${current_price:,.2f}", flush=True)
                    
                    # Send telegram message 5 times spaced out over 5 minutes
                    for i in range(5):
                        msg = (
                            f"🚨 <b>BTC SWEEP ALERT ({i+1}/5)</b> 🚨\n\n"
                            f"BTC has hit <b>${current_price:,.2f}</b>, sweeping the {direction}.\n\n"
                            f"Target level was ${target_hit:,.2f}. Check charts for a reaction!"
                        )
                        notifier._send_message(msg)
                        print(f"Sent Telegram Alert {i+1}/5", flush=True)
                        
                        if i < 4:
                            time.sleep(60) # wait 1 minute before sending next
                    break
                else:
                    dist_upper = target_upper - current_price
                    dist_lower = current_price - target_lower
                    print(f"⌛ {timestamp} | BTC: ${current_price:,.2f} | To Upper: ${dist_upper:,.0f} | To Lower: ${dist_lower:,.0f}    ", end="\r", flush=True)
            
            time.sleep(30) # Check every 30 seconds
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped.")

if __name__ == "__main__":
    monitor_sweep()
