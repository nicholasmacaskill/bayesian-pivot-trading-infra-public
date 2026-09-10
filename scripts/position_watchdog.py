import os
import sys
import time
import json
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.getcwd())

from src.clients.tl_client import TradeLockerClient
from src.clients.telegram_notifier import TelegramNotifier
from src.core.supabase_client import SupabaseBridge

class PositionWatchdog:
    def __init__(self):
        load_dotenv(".env.local")
        self.tl = TradeLockerClient()
        self.sb = SupabaseBridge()
        self.notifier = TelegramNotifier()
        self.alerted_trades = {} # {trade_id: {r_level: bool}}
        self.load_state()

    def load_state(self):
        try:
            if os.path.exists("watchdog_state.json"):
                with open("watchdog_state.json", "r") as f:
                    self.alerted_trades = json.load(f)
        except Exception as e:
            print(f"Error loading state: {e}")

    def save_state(self):
        try:
            with open("watchdog_state.json", "w") as f:
                json.dump(self.alerted_trades, f, indent=4)
        except Exception as e:
            print(f"Error saving state: {e}")

    def get_stop_loss(self, symbol):
        """Find the Stop Loss from the last ACCEPTED scan in Supabase."""
        try:
            # Query for the latest ACCEPTED scan for this symbol in the last 24h
            time_threshold = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            resp = self.sb.client.table("scans")\
                .select("*")\
                .eq("symbol", symbol)\
                .eq("verdict", "ACCEPTED")\
                .gt("timestamp", time_threshold)\
                .order("timestamp", desc=True)\
                .limit(1)\
                .execute()
            
            if resp.data:
                # We need to extract the raw data, sometimes it's in ai_payload or raw columns
                scan = resp.data[0]
                # Try common locations for SL
                sl = scan.get('stop_loss')
                if not sl and scan.get('ai_payload'):
                    try:
                        payload = json.loads(scan['ai_payload'])
                        sl = payload.get('stop_loss')
                    except: pass
                
                return float(sl) if sl else None, scan
        except Exception as e:
            print(f"Error fetching SL for {symbol}: {e}")
        return None, None

    def run(self):
        print("🛡️ Bayesian Pivot Watchdog starting...")
        print("Monitoring for R-multiple targets (1.5R, 2.0R)...")
        
        while True:
            try:
                positions = self.tl.get_open_positions()
                if not positions:
                    print("No open positions found.")
                
                for pos in positions:
                    t_id = pos['id']
                    symbol = pos['symbol']
                    entry = pos['price']
                    pnl = pos['pnl']
                    side = pos['side']
                    
                    if t_id not in self.alerted_trades:
                        self.alerted_trades[t_id] = {}

                    # 1. Fetch SL
                    sl, scan = self.get_stop_loss(symbol)
                    if not sl:
                        print(f"Could not find SL for {symbol} trade {t_id}. Skipping R calculation.")
                        continue
                    
                    # 2. Calculate R
                    # risk_dist = abs(entry - sl)
                    qty = pos.get('qty', 0)
                    
                    # Try to find the original Risk USD from the scan
                    risk_usd = 0
                    if scan.get('ai_payload'):
                        try:
                            # Re-parse the fuller scan object if needed
                            payload = json.loads(scan['ai_payload'])
                            risk_usd = payload.get('risk_usd', 0)
                        except: pass
                    
                    if not risk_usd or risk_usd == 0:
                        # Fallback: Calculate from SL and QTY
                        # Note: This requires knowing the contract size (e.g., 100k for FX, 1 for BTC)
                        contract_size = 100000 if "USD" in symbol and "BTC" not in symbol else 1
                        risk_usd = abs(entry - sl) * qty * contract_size
                    
                    if not risk_usd or risk_usd == 0:
                        print(f"Could not determine risk for {symbol}. PnL: ${pnl}")
                        continue
                    
                    r_multiple = pnl / risk_usd
                    
                    print(f"[{symbol}] PnL: ${pnl:.2f} | Risk: ${risk_usd:.2f} | R: {r_multiple:.2f}")

                    # 3. Alert & Automated Fleet Scale-Out Logic
                    if r_multiple >= 1.5 and not self.alerted_trades.get(t_id, {}).get("scaleout_executed"):
                        print(f"💰 [AUTO SCALE-OUT] {symbol} hit {r_multiple:.2f}R! Executing 50% Fleet Scale-Out...")
                        self.execute_fleet_scaleout(symbol, entry)
                        self.alerted_trades[t_id]["scaleout_executed"] = True
                        self.save_state()

                    for target in [1.5, 2.0, 3.0]:
                        target_key = str(target)
                        if r_multiple >= target and not self.alerted_trades.get(t_id, {}).get(target_key):
                            msg = (
                                f"🚀 <b>BAYESIAN PIVOT TARGET REACHED!</b>\n"
                                f"Symbol: <code>{symbol}</code>\n"
                                f"Current R: <b>{r_multiple:.2f}R</b>\n\n"
                                f"🛡️ <b>DISCIPLINE CHECK:</b> You've hit {target}R. "
                                "This is where the 'Break-even Trap' happens. \n\n"
                                "<b>WALK AWAY</b>. Let the system manage the rest or hold for the next target."
                            )
                            self.notifier._send_message(msg)
                            self.alerted_trades[t_id][target_key] = True
                            self.save_state()

            except Exception as e:
                print(f"Watchdog Loop Error: {e}")
            
            time.sleep(60) # Poll every 60s

    def execute_fleet_scaleout(self, symbol: str, entry_price: float):
        """
        Automated 50/50 Fleet Partitioning Scale-Out (Strict AGENTS.md Compliance):
        - Accounts 0-3 (50% Fleet): Closes positions via DELETE /positions/{id} to realize cash profit.
        - Accounts 4-7 (50% Fleet): Moves SL to Break-Even via PATCH /positions/{id} to let runners ride risk-free.
        """
        try:
            close_accounts = [0, 1, 2, 3]
            trail_accounts = [4, 5, 6, 7]
            closed_count = 0
            trailed_count = 0
            
            # 1. Close Accounts 0, 1, 2, 3
            for acc_idx in close_accounts:
                if acc_idx >= len(self.tl.helpers):
                    continue
                helper = self.tl.helpers[acc_idx]
                if not helper.access_token and not helper.login():
                    continue
                positions = helper.get_open_positions()
                target_pos = [p for p in positions if str(p.get("symbol", "")).upper() == symbol.upper() or "BTC" in str(p.get("symbol", "")).upper()]
                for pos in target_pos:
                    pos_id = pos.get("id") or pos.get("positionId")
                    if helper.close_position(pos_id):
                        closed_count += 1
                time.sleep(2.0) # Adaptive 2.0s pacing between accounts

            # 2. Trail Stop Loss on Accounts 4, 5, 6, 7 to Entry (Break-Even)
            for acc_idx in trail_accounts:
                if acc_idx >= len(self.tl.helpers):
                    continue
                helper = self.tl.helpers[acc_idx]
                if not helper.access_token and not helper.login():
                    continue
                positions = helper.get_open_positions()
                target_pos = [p for p in positions if str(p.get("symbol", "")).upper() == symbol.upper() or "BTC" in str(p.get("symbol", "")).upper()]
                for pos in target_pos:
                    pos_id = pos.get("id") or pos.get("positionId")
                    if helper.modify_position_bracket(pos_id, stop_loss=float(entry_price)):
                        trailed_count += 1
                time.sleep(2.0) # Adaptive 2.0s pacing between accounts

            scaleout_msg = (
                f"💰 <b>AUTONOMOUS 50% FLEET SCALE-OUT EXECUTED</b>\n\n"
                f"Symbol: <code>{symbol}</code>\n"
                f"Trigger: <b>+1.5R Reached</b>\n\n"
                f"🏦 <b>Realized Cash Profit:</b> Closed {closed_count} accounts (Acc 0-3)\n"
                f"🛡️ <b>Risk-Free Trailing:</b> Moved SL to Break-Even (${entry_price:,.2f}) on {trailed_count} accounts (Acc 4-7)\n\n"
                f"<i>Invariant: Zero risk remaining. Runners targeting full Take Profit.</i>"
            )
            self.notifier._send_message(scaleout_msg)
            print(f"✅ Fleet Scale-Out Complete: Closed={closed_count}, Trailed={trailed_count}")
        except Exception as e:
            print(f"Error executing fleet scaleout: {e}")

if __name__ == "__main__":
    PositionWatchdog().run()
