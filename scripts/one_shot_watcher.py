
import sys
import os
import time
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def monitor_one_shot():
    scanner = SMCScanner()
    symbol = "BTC/USD"
    target_entry = 69050
    stop_loss = 68650
    take_profit = 73750
    lot_size = 0.75
    
    print(f"🎯 Sovereign Watcher: Monitoring for Prop Firm One-Shot Entry...", flush=True)
    print(f"📊 Target Entry: ${target_entry:,}", flush=True)
    print(f"🛡️ Stop Loss: ${stop_loss:,}", flush=True)
    print(f"🚀 Take Profit: ${take_profit:,}", flush=True)
    print(f"📦 Position Size: {lot_size} BTC", flush=True)
    print("-" * 50, flush=True)

    try:
        while True:
            df = scanner.fetch_data(symbol, "1m", limit=5)
            if df is not None:
                current_price = df.iloc[-1]['close']
                timestamp = datetime.now().strftime("%H:%M:%S")
                
                # Check if entry is hit
                if current_price <= target_entry:
                    print(f"\n🔔 [TRIGGERED] {timestamp} | BTC at ${current_price:,.2f}", flush=True)
                    print(f"✅ ENTRY ZONE REACHED (${target_entry})", flush=True)
                    print(f"👉 EXECUTION: LONG {lot_size} BTC", flush=True)
                    print(f"👉 SL: {stop_loss} | TP: {take_profit}", flush=True)
                    break
                else:
                    dist = current_price - target_entry
                    print(f"⌛ {timestamp} | BTC: ${current_price:,.2f} | Distance to Entry: ${dist:,.2f}", end="\r", flush=True)
            
            time.sleep(30) # Check every 30 seconds
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped.")

if __name__ == "__main__":
    monitor_one_shot()
