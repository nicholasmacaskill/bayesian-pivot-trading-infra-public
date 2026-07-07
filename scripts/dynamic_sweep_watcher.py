import sys
import os
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner
from src.clients.telegram_notifier import TelegramNotifier
from src.clients.tl_client import TradeLockerClient
from src.core.config import Config

def get_dynamic_targets(scanner, symbol="BTC/USD"):
    """
    Dynamically scans the market, extracts the active session liquidity ranges,
    and determines the closest external liquidity magnets.
    """
    quartiles = scanner.get_price_quartiles(symbol)
    if not quartiles:
        return None, None
    
    # Extract the Asian Range High and Low (primary magnets)
    # If Asian isn't available, fallback to London
    asian = quartiles.get("Asian Range", {})
    london = quartiles.get("London Range", {})
    cbdr = quartiles.get("CBDR", {})
    
    upper_target = None
    lower_target = None
    
    # Find the highest BSL and lowest SSL from recent sessions to trap
    highs = []
    lows = []
    
    for session in [asian, london, cbdr]:
        if 'high' in session: highs.append(session['high'])
        if 'low' in session: lows.append(session['low'])
        
    if highs and lows:
        upper_target = max(highs)  # The ultimate Buy-Side Liquidity trap
        lower_target = min(lows)   # The ultimate Sell-Side Liquidity trap
        
    return upper_target, lower_target

def run_dynamic_daemon():
    load_dotenv('.env.local')
    scanner = SMCScanner()
    notifier = TelegramNotifier()
    tl_client = TradeLockerClient()
    symbol = "BTC/USD"
    
    print("🤖 Autonomous Target Daemon Initialized.", flush=True)
    
    while True:
        local_tz = timezone(timedelta(hours=-3))
        now_str = datetime.now(timezone.utc).astimezone(local_tz).strftime('%H:%M:%S')
        print(f"\n🔄 [{now_str}] Running Full Market Scan...", flush=True)
        upper, lower = get_dynamic_targets(scanner, symbol)
        
        if not upper or not lower:
            print("⚠️ Could not fetch market structure. Retrying in 5 minutes...", flush=True)
            time.sleep(300)
            continue
            
        print(f"🎯 Dynamic Targets Locked:")
        print(f"   📈 Upper (BSL Trap): >= ${upper:,.2f}")
        print(f"   📉 Lower (SSL Trap): <= ${lower:,.2f}")
        print("-" * 50, flush=True)
        
        # Track if we need to reset the targets
        targets_hit = False
        scan_timer = 0
        
        # Poll the 1-minute chart
        while not targets_hit:
            df = scanner.fetch_data(symbol, "1m", limit=5)
            if df is not None:
                current_price = df.iloc[-1]['close']
                
                # Convert server time to UTC-3 (User's Local Time)
                local_tz = timezone(timedelta(hours=-3))
                timestamp = datetime.now(timezone.utc).astimezone(local_tz).strftime("%H:%M:%S")
                
                trigger_type = None
                target_hit = None
                
                if current_price >= upper:
                    trigger_type = "UPPER"
                    target_hit = upper
                elif current_price <= lower:
                    trigger_type = "LOWER"
                    target_hit = lower
                
                if trigger_type:
                    # Optimized Risk Management for $250 Profit with Wide Stop
                    # Using 0.25 BTC: 1000 point move = $250. 300 point SL = $75 Risk.
                    qty = 0.25
                    if trigger_type == "UPPER":
                        side = "sell"
                        sl = current_price + 300
                        tp = current_price - 1000
                        direction = "Buy-Side Liquidity (Short Trap)"
                    else:
                        side = "buy"
                        sl = current_price - 300
                        tp = current_price + 1000
                        direction = "Sell-Side Liquidity (Long Trap)"
                        
                    print(f"\n🔔 [{trigger_type} TRIGGERED] BTC at ${current_price:,.2f}", flush=True)
                    
                    # --- CYBORG MODE: AUTO-EXECUTION DISABLED ---
                    print(f"🤖 [CYBORG MODE] Alerting {qty} BTC {side.upper()} opportunity (Execution Disabled)...", flush=True)
                    status_text = "⚠️ CYBORG MODE: AUTO-EXECUTION DISABLED. MANUAL CONFIRMATION REQUIRED."
                    
                    # 5-Message Alert Sequence
                    for i in range(5):
                        msg = (
                            f"🚨 <b>BAYESIAN PIVOT ALERT ({i+1}/5)</b> 🚨\n\n"
                            f"BTC hit <b>${current_price:,.2f}</b>, sweeping the {direction}.\n\n"
                            f"<b>{status_text}</b>\n\n"
                            f"Suggested Action: {side.upper()} {qty} BTC\n"
                            f"Suggested Stop Loss: ${sl:,.2f}\n"
                            f"Suggested Take Profit: ${tp:,.2f}"
                        )
                        notifier._send_message(msg)
                        print(f"   Sent Alert {i+1}/5", flush=True)
                        if i < 4:
                            time.sleep(60)
                            
                    targets_hit = True # Break inner loop, trigger full rescan
                    print("💤 Cooling down for 60 minutes before resetting traps...", flush=True)
                    time.sleep(3600) # Wait 1 hour after a sweep before re-arming
                    break
                else:
                    dist_up = upper - current_price
                    dist_dn = current_price - lower
                    print(f"⌛ {timestamp} | BTC: ${current_price:,.0f} | To BSL: ${dist_up:,.0f} | To SSL: ${dist_dn:,.0f}    ", end="\r", flush=True)
            
            time.sleep(30)
            scan_timer += 30
            
            # Re-scan market structure automatically every 4 hours just in case ranges shifted
            if scan_timer >= 14400:
                print("\n⏰ 4-Hour Rescan Triggered. Recalculating traps...", flush=True)
                break 

if __name__ == "__main__":
    try:
        run_dynamic_daemon()
    except KeyboardInterrupt:
        print("\n🛑 Dynamic Monitoring stopped.")
