import sys
import os
import time
import argparse
import logging

# Fix ModuleNotFoundError: No module named 'src'
sys.path.append(os.getcwd())

from src.core.config import Config
from src.engines.alpha_sweep_scanner import AlphaSweepScanner

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def run_scanner(test_mode=False):
    scanner = AlphaSweepScanner()
    symbols = Config.SYMBOLS
    
    logger.info(f"Starting Sovereign Alpha Sweep Scanner. Symbols: {symbols} | Test Mode: {test_mode}")
    
    if test_mode:
        # Override is_premium_killzone to return a dummy value
        scanner.is_premium_killzone = lambda *args, **kwargs: "TEST_MODE_RUN"
        
    for symbol in symbols:
        try:
            logger.info(f"Scanning symbol: {symbol}")
            setup = scanner.scan_symbol(symbol)
            if setup:
                logger.info(f"🏆 Found setup for {symbol}: {setup}")
            else:
                logger.info(f"No setup found for {symbol}.")
        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}", exc_info=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sovereign Alpha Sweep Scanner Runner")
    parser.add_argument("--test", action="store_true", help="Run once in test mode, overriding Killzone time gates")
    parser.add_argument("--loop", action="store_true", help="Run in a loop every interval minutes")
    
    args = parser.parse_args()
    
    if args.loop:
        interval = Config.get("RUN_INTERVAL_MINS", 3) * 60
        logger.info(f"Starting loop mode, running every {Config.get('RUN_INTERVAL_MINS', 3)} minutes.")
        while True:
            run_scanner(test_mode=args.test)
            logger.info(f"Sleeping for {Config.get('RUN_INTERVAL_MINS', 3)} minutes...")
            time.sleep(interval)
    else:
        run_scanner(test_mode=args.test)
