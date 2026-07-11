import sys
import os
import time
from dotenv import load_dotenv

sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.clients.telegram_notifier import TelegramNotifier

def main():
    load_dotenv('.env.local')
    scanner = SMCScanner()
    notifier = TelegramNotifier()
    symbol = "BTC/USD"
    target = 63000.00
    
    print(f"🎯 Sovereign Custom Watcher: Monitoring for BTC to drop to ${target:,.2f}...", flush=True)
    
    while True:
        df = scanner.fetch_data(symbol, "1m", limit=5)
        if df is not None:
            current_price = df.iloc[-1]['close']
            if current_price <= target:
                msg = (
                    f"🚨 <b>CUSTOM LONG ALERT</b> 🚨\n\n"
                    f"BTC has dropped into your target zone!\n"
                    f"Current price: <b>${current_price:,.2f}</b> (Target was ${target:,.2f})\n\n"
                    f"Watch lower timeframes for a Market Structure Shift (MSS) before entering."
                )
                notifier._send_message(msg)
                print(f"\n🔔 Alert sent! BTC hit {current_price}", flush=True)
                break
            else:
                dist = current_price - target
                print(f"⌛ BTC: ${current_price:,.0f} | To Target: ${dist:,.0f}    ", end="\r", flush=True)
        time.sleep(30)

if __name__ == "__main__":
    main()
