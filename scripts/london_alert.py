#!/usr/bin/env python3
import sys
import os
import time
import logging
from datetime import datetime

# Ensure project root is in path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from src.clients.telegram_notifier import TelegramNotifier
from src.engines.smc_scanner import SMCScanner
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/london_alert.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("LondonAlert")

# Target Levels
SSL_LEVEL = 67085.66
BSL_LEVEL = 68223.07
SYMBOL = "BTC/USD"

def monitor_levels():
    notifier = TelegramNotifier()
    scanner = SMCScanner()
    
    logger.info(f"🚀 Starting London Open Price Watcher for {SYMBOL}")
    logger.info(f"🔴 SSL Alert Level: ${SSL_LEVEL:,.2f}")
    logger.info(f"🟢 BSL Alert Level: ${BSL_LEVEL:,.2f}")
    
    # Send initial confirmation to Telegram
    init_msg = (
        f"🦁 *London Open Watcher Active*\n\n"
        f"I'm now monitoring `{SYMBOL}` for the Judas Swing levels:\n"
        f"🔴 *SSL (Lower):* `${SSL_LEVEL:,.2f}`\n"
        f"🟢 *BSL (Upper):* `${BSL_LEVEL:,.2f}`\n\n"
        f"I will alert you as soon as either level is swept."
    )
    notifier._send_message(init_msg)
    
    alerted_ssl = False
    alerted_bsl = False
    
    while True:
        try:
            # Fetch current price
            df = scanner.fetch_data(SYMBOL, '1m', limit=5)
            if df is None or df.empty:
                time.sleep(10)
                continue
                
            current_price = df['close'].iloc[-1]
            logger.info(f"💎 BTC Current Price: ${current_price:,.2f}")
            
            # Check SSL Sweep
            if current_price < SSL_LEVEL and not alerted_ssl:
                logger.info("🚨 SSL LEVEL SWEPT!")
                msg = (
                    f"🚨 *SSL LEVEL SWEPT!* 🚨\n\n"
                    f"BTC has dropped below `${SSL_LEVEL:,.2f}`.\n"
                    f"Current Price: `${current_price:,.2f}`\n\n"
                    f"💡 *Play:* Watch for a 5m reclaim and displacement back above for Scenario A (Long)."
                )
                notifier._send_message(msg)
                alerted_ssl = True
                
            # Check BSL Sweep
            if current_price > BSL_LEVEL and not alerted_bsl:
                logger.info("🚨 BSL LEVEL SWEPT!")
                msg = (
                    f"🚨 *BSL LEVEL SWEPT!* 🚨\n\n"
                    f"BTC has spiked above `${BSL_LEVEL:,.2f}`.\n"
                    f"Current Price: `${current_price:,.2f}`\n\n"
                    f"💡 *Play:* Watch for a rejection and close back below for Scenario B (Short)."
                )
                notifier._send_message(msg)
                alerted_bsl = True
                
            # Reset alerts if price moves significantly back inside range? 
            # (Maybe not necessary for a one-night monitor)
            
            # Poll every 15 seconds
            time.sleep(15)
            
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    monitor_levels()
