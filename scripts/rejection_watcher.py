import sys
import os
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.clients.telegram_notifier import TelegramNotifier

def run_rejection_watcher():
    load_dotenv('.env')
    load_dotenv('.env.local')
    
    scanner = SMCScanner()
    notifier = TelegramNotifier()
    symbol = "BTC/USD"
    
    # 1. Fetch range targets
    quartiles = scanner.get_price_quartiles(symbol)
    if not quartiles:
        print("❌ Error: Could not calculate range levels.")
        return
        
    asian_high_sd1 = quartiles.get("Asian Range", {}).get("sd_1_pos", 66617.9)
    london_high_sd1 = quartiles.get("London Range", {}).get("sd_1_pos", 66476.3)
    
    print("🤖 Rejection Alert Watcher Initialized.")
    print(f"   📐 Asian High SD+1 Level: ${asian_high_sd1:,.2f}")
    print(f"   📐 London High SD+1 Level: ${london_high_sd1:,.2f}")
    print("   Monitoring 5m candles for sweep & close-back-below rejection...")
    print("-" * 60, flush=True)
    
    # Send initialization message to user
    init_msg = (
        f"⏳ <b>REJECTION WATCHER ACTIVE</b>\n\n"
        f"Traps armed above:\n"
        f"• Asian High SD+1: <code>${asian_high_sd1:,.2f}</code>\n"
        f"• London High SD+1: <code>${london_high_sd1:,.2f}</code>\n\n"
        f"I will alert you on Telegram the instant a 5-minute candle sweeps and closes back below."
    )
    notifier._send_message(init_msg)
    
    last_processed_timestamp = None
    
    while True:
        try:
            # Fetch last few 5m candles to see completed closed candles
            df = scanner.fetch_data(symbol, "5m", limit=5, synchronized=False)
            if df is not None and len(df) >= 2:
                # The latest completed candle is the second to last index (df.iloc[-2])
                # since the last index is the currently active/forming candle.
                candle = df.iloc[-2]
                candle_time = candle['timestamp']
                
                if candle_time != last_processed_timestamp:
                    c_open = candle['open']
                    c_high = candle['high']
                    c_low = candle['low']
                    c_close = candle['close']
                    
                    # Check if the candle swept either of the levels
                    swept_level = None
                    level_name = ""
                    
                    if c_high > asian_high_sd1:
                        swept_level = asian_high_sd1
                        level_name = "Asian Range High SD+1"
                    elif c_high > london_high_sd1:
                        swept_level = london_high_sd1
                        level_name = "London Range High SD+1"
                        
                    # Rejection condition: Swept the level AND closed back below it AND closed bearish
                    if swept_level and c_close < swept_level and c_close < c_open:
                        # Rejection confirmed!
                        local_tz = timezone(timedelta(hours=-3))
                        timestamp = datetime.now(timezone.utc).astimezone(local_tz).strftime("%H:%M:%S")
                        
                        # Stop Loss is set just above the high of the sweep candle
                        sl = c_high + 50.0
                        # Risk distance
                        risk = sl - c_close
                        # 1:3 Reward target
                        tp = c_close - (risk * 3.0)
                        
                        msg = (
                            f"🚨 <b>BEARISH REJECTION CONFIRMED ({timestamp} AST)</b> 🚨\n\n"
                            f"BTC swept the <b>{level_name} (${swept_level:,.2f})</b>!\n\n"
                            f"• Candle High: <code>${c_high:,.2f}</code>\n"
                            f"• Candle Close: <code>${c_close:,.2f}</code> (Rejection confirmed)\n\n"
                            f"📐 <b>Suggested Low-Risk Setup:</b>\n"
                            f"• <b>Entry (Short):</b> <code>${c_close:,.2f}</code>\n"
                            f"• <b>Stop Loss:</b> <code>${sl:,.2f}</code>\n"
                            f"• <b>Take Profit (1:3 RR):</b> <code>${tp:,.2f}</code>\n\n"
                            f"Manual action required to execute on TradeLocker."
                        )
                        print(f"\n📢 TRIGGERED: {level_name} rejection at ${c_close:,.2f}", flush=True)
                        notifier._send_message(msg)
                        
                        # Set to avoid double-triggering on same candle
                        last_processed_timestamp = candle_time
                        
                        # Exit watcher after a successful trigger to prevent spam
                        print("Watcher job complete. Exiting.", flush=True)
                        break
                    
                    # Update timestamp even if no trigger to mark it processed
                    last_processed_timestamp = candle_time
                    
                    local_tz = timezone(timedelta(hours=-3))
                    now_str = datetime.now(timezone.utc).astimezone(local_tz).strftime("%H:%M:%S")
                    print(f"⌛ [{now_str}] Checked candle {candle_time.strftime('%H:%M')} | Close: ${c_close:,.2f} | High: ${c_high:,.2f} | No Rejection", flush=True)
            
            # Poll every 15 seconds
            time.sleep(15)
            
        except Exception as e:
            print(f"Error in rejection watcher loop: {e}", flush=True)
            time.sleep(15)

if __name__ == "__main__":
    try:
        run_rejection_watcher()
    except KeyboardInterrupt:
        print("\n🛑 Rejection Watcher stopped.")
