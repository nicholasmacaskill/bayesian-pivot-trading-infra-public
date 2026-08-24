#!/usr/bin/env python3
"""
Strategy 9: Judas Inducement Hunter — Standalone Dedicated Runner
================================================================
Monitors 5m candle streams across target symbols (BTC/USD, ETH/USD, SOL/USD),
evaluates exact 70%+ rejection wicks and 1.8x+ ATR spikes, and executes directly
to TradeLocker with zero generic filter bottlenecks.

Usage:
  # Run live with auto-execution
  python3 scripts/run_strategy9_standalone.py

  # Run in dry-run (simulation/alert-only) mode
  python3 scripts/run_strategy9_standalone.py --dry-run
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime, timezone

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.config import Config
from src.engines.smc_scanner import SMCScanner
from src.engines.judas_inducement_engine import JudasInducementEngine
from src.clients.tl_client import TradeLockerClient
from src.clients.telegram_notifier import TelegramNotifier

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [Strategy9-Hunter] - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Strategy9Runner")


def main():
    parser = argparse.ArgumentParser(description="Strategy 9 Standalone Runner")
    parser.add_argument("--dry-run", action="store_true", help="Run without sending live broker orders")
    parser.add_argument("--interval", type=int, default=60, help="Polling interval in seconds (default: 60)")
    args = parser.parse_args()

    symbols = [s for s in Config.SYMBOLS if "XAU" not in s]
    if "SOL/USD" not in symbols:
        symbols.append("SOL/USD")

    print("=" * 80)
    print(" ⚡ STRATEGY 9: JUDAS INDUCEMENT HUNTER (70% WICK FADE) — DEDICATED RUNNER")
    print(f" Mode: {'DRY-RUN (Alerts Only)' if args.dry_run else 'LIVE AUTO-EXECUTION'}")
    print(f" Target Symbols: {symbols}")
    print(f" Parameters: Min Wick >= {Config.STRATEGY_9_MIN_WICK_PCT}% | Min Range >= {Config.STRATEGY_9_MIN_ATR_MULT}x ATR | Target: {Config.STRATEGY_9_TARGET_RR}R")
    print("=" * 80)


    scanner = SMCScanner()
    engine = JudasInducementEngine()
    notifier = TelegramNotifier()
    tl_client = TradeLockerClient() if not args.dry_run else None

    seen_candles = set()

    try:
        while True:
            for symbol in Config.SYMBOLS:
                try:
                    df = scanner.fetch_data(symbol, timeframe="5m", limit=35)
                    if df is None or len(df) < 25:
                        continue

                    last_candle_ts = str(df.iloc[-1].get('timestamp', ''))
                    candle_key = f"{symbol}_{last_candle_ts}"

                    if candle_key in seen_candles:
                        continue

                    # Evaluate candle for Strategy 9 setup
                    setup = engine.evaluate_dataframe(df, symbol=symbol)
                    seen_candles.add(candle_key)

                    # Keep memory bounded
                    if len(seen_candles) > 1000:
                        seen_candles = set(list(seen_candles)[-500:])

                    if setup:
                        logger.info(f"🚨 [SETUP TRIGGERED] {symbol} {setup['direction']} (Wick: {setup['wick_pct']}%)")
                        
                        # 1. Send Telegram Alert
                        alert_msg = engine.format_telegram_alert(setup)
                        if args.dry_run:
                            alert_msg = "<b>[🧪 DRY-RUN SIMULATION]</b>\n" + alert_msg
                        notifier._send_message(alert_msg)

                        # 2. Live Broker Execution
                        if not args.dry_run and tl_client:
                            exec_side = "buy" if setup['direction'] == "LONG" else "sell"
                            lots = setup['calculated_lots']
                            sl = setup['stop_loss']
                            tp = setup['take_profit']

                            logger.info(f"⚡ Submitting TradeLocker Order: {exec_side.upper()} {lots} lots of {symbol} (SL: ${sl:,.2f}, TP: ${tp:,.2f})")
                            success = tl_client.execute_trade(
                                symbol=symbol,
                                side=exec_side,
                                qty=lots,
                                stop_loss=sl,
                                take_profit=tp
                            )
                            if success:
                                logger.info(f"✅ Trade placed successfully on TradeLocker!")
                                notifier._send_message(f"⚡ <b>BROKER ORDER CONFIRMED:</b> {exec_side.upper()} {lots} lots of {symbol} active.")
                            else:
                                logger.error("❌ Broker order was rejected by TradeLocker.")
                                notifier._send_message(f"⚠️ <b>BROKER ORDER REJECTED</b> for {symbol}.")

                except Exception as sym_err:
                    logger.debug(f"Error evaluating {symbol}: {sym_err}")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n🛑 Strategy 9 Standalone Runner stopped cleanly.")


if __name__ == "__main__":
    main()
