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
from src.core.config import Config

STATE_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "watchdog_state.json"
)

class PositionWatchdog:
    def __init__(self):
        self.tl = TradeLockerClient()
        self.sb = SupabaseBridge()
        self.notifier = TelegramNotifier()
        self.alerted_trades = {} # {trade_id: {r_level: bool}}
        self.symbol_state = {}   # {clean_sym: {scaleout_executed: bool, peak_r: float, ...}}
        self.load_state()

    def load_state(self):
        try:
            if os.path.exists(STATE_FILE_PATH):
                with open(STATE_FILE_PATH, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.alerted_trades = data.get("alerted_trades", {})
                        self.symbol_state = data.get("symbol_state", {})
                        # Backward compatibility if data was a flat alerted_trades dict
                        if not self.alerted_trades and not self.symbol_state:
                            self.alerted_trades = data
        except Exception as e:
            print(f"Error loading state: {e}")

    def save_state(self):
        try:
            os.makedirs(os.path.dirname(STATE_FILE_PATH), exist_ok=True)
            with open(STATE_FILE_PATH, "w") as f:
                json.dump({
                    "alerted_trades": self.alerted_trades,
                    "symbol_state": self.symbol_state
                }, f, indent=4)
        except Exception as e:
            print(f"Error saving state: {e}")

    def get_stop_loss(self, symbol, pos=None):
        """Find the Stop Loss directly from the open position object, or fallback to Supabase."""
        # 1. Primary: Broker position attached stopLoss
        if pos and pos.get('stopLoss'):
            try:
                val = float(pos['stopLoss'])
                if val > 0:
                    return val, None
            except (ValueError, TypeError):
                pass

        # 2. Secondary: Fallback to Supabase scans
        try:
            norm_sym = symbol
            if "/" not in norm_sym:
                if "BTC" in norm_sym: norm_sym = "BTC/USD"
                elif "ETH" in norm_sym: norm_sym = "ETH/USD"
                elif "SOL" in norm_sym: norm_sym = "SOL/USD"
                elif "XAU" in norm_sym: norm_sym = "XAU/USD"
                elif len(norm_sym) == 6: norm_sym = f"{norm_sym[:3]}/{norm_sym[3:]}"

            time_threshold = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            resp = self.sb.client.table("scans")\
                .select("*")\
                .eq("symbol", norm_sym)\
                .eq("verdict", "ACCEPTED")\
                .gt("timestamp", time_threshold)\
                .order("timestamp", desc=True)\
                .limit(1)\
                .execute()
            
            if resp.data:
                scan = resp.data[0]
                sl = scan.get('stop_loss')
                if not sl and scan.get('ai_payload'):
                    try:
                        payload = json.loads(scan['ai_payload'])
                        sl = payload.get('stop_loss')
                    except: pass
                
                if sl:
                    return float(sl), scan
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
                    if self.symbol_state or self.alerted_trades:
                        self.symbol_state.clear()
                        self.alerted_trades.clear()
                        self.save_state()
                
                for pos in positions:
                    t_id = pos['id']
                    symbol = pos['symbol']
                    clean_sym = symbol.replace("/", "").replace("_", "").upper()
                    entry = float(pos.get('price') or 0.0)
                    pnl = float(pos.get('pnl') or 0.0)
                    side = pos.get('side', 'BUY')
                    
                    if t_id not in self.alerted_trades:
                        self.alerted_trades[t_id] = {}

                    sym_data = self.symbol_state.setdefault(clean_sym, {
                        "scaleout_executed": False,
                        "mfe_scaleout_executed": False,
                        "macro_scaleout_executed": False,
                        "peak_r": 0.0,
                        "milestones": {}
                    })

                    # 1. Fetch SL directly from broker position or fallback
                    sl, scan = self.get_stop_loss(symbol, pos=pos)
                    if not sl or entry <= 0:
                        continue
                    
                    # 2. Calculate R
                    qty = float(pos.get('qty') or 0.0)
                    contract_size = Config.get_contract_size(symbol)
                    risk_usd = abs(entry - sl) * qty * contract_size
                    
                    if not risk_usd or risk_usd <= 0:
                        continue
                    
                    r_multiple = pnl / risk_usd
                    print(f"[{symbol}] PnL: ${pnl:.2f} | Risk: ${risk_usd:.2f} | R: {r_multiple:.2f}")

                    # 3. Peak R-Multiple Tracking & Immediate State Persistence
                    peak_r = max(
                        sym_data.get("peak_r", 0.0),
                        self.alerted_trades.get(t_id, {}).get("peak_r", 0.0),
                        r_multiple
                    )
                    if peak_r > sym_data.get("peak_r", 0.0):
                        sym_data["peak_r"] = peak_r
                        self.alerted_trades[t_id]["peak_r"] = peak_r
                        self.save_state()

                    # 4. Standard Automated Fleet Scale-Out at BE Trigger (+1.5R) (Deduplicated per Symbol)
                    be_trigger = getattr(Config, 'BE_TRIGGER_R', 1.5)
                    is_scaled_out = sym_data.get("scaleout_executed") or self.alerted_trades.get(t_id, {}).get("scaleout_executed")
                    if r_multiple >= be_trigger and not is_scaled_out:
                        print(f"💰 [AUTO SCALE-OUT] {symbol} hit {r_multiple:.2f}R! Executing Fleet Break-Even & Scale-Out...")
                        self.execute_fleet_scaleout(symbol, entry, reason=f"+{be_trigger:.1f}R Target Reached")
                        sym_data["scaleout_executed"] = True
                        self.alerted_trades[t_id]["scaleout_executed"] = True
                        self.save_state()

                    # 5. MFE Peak Retracement Ratchet (Deduplicated per Symbol)
                    mfe_enabled = getattr(Config, 'MFE_PEAK_RATCHET_ENABLED', True)
                    mfe_min_peak = getattr(Config, 'MFE_MIN_PEAK_R', 2.0)
                    mfe_max_retrace = getattr(Config, 'MFE_MAX_RETRACEMENT_R', 0.75)
                    is_mfe_scaled = sym_data.get("mfe_scaleout_executed") or self.alerted_trades.get(t_id, {}).get("mfe_scaleout_executed")
                    if mfe_enabled and peak_r >= mfe_min_peak:
                        retrace = peak_r - r_multiple
                        if retrace >= mfe_max_retrace and not is_mfe_scaled:
                            print(f"🛡️ [MFE PEAK RATCHET] {symbol} peaked at +{peak_r:.2f}R, retraced {retrace:.2f}R (now {r_multiple:.2f}R)! Executing defensive scale-out...")
                            self.execute_fleet_scaleout(symbol, entry, reason=f"MFE Peak Retracement (+{peak_r:.2f}R -> +{r_multiple:.2f}R)")
                            sym_data["mfe_scaleout_executed"] = True
                            self.alerted_trades[t_id]["mfe_scaleout_executed"] = True
                            self.save_state()

                    # 6. Pre-Macro Event Defense (Deduplicated per Symbol)
                    macro_enabled = getattr(Config, 'MACRO_DEFENSE_ENABLED', True)
                    macro_min_r = getattr(Config, 'MACRO_DEFENSE_MIN_R', 1.0)
                    is_macro_scaled = sym_data.get("macro_scaleout_executed") or self.alerted_trades.get(t_id, {}).get("macro_scaleout_executed")
                    if macro_enabled and r_multiple >= macro_min_r and not is_macro_scaled:
                        try:
                            from src.engines.calendar_filter import CalendarFilter
                            is_safe, cal_reason = CalendarFilter().is_safe_to_trade(symbol)
                            if not is_safe and "⛔ MACRO BLACKOUT" in str(cal_reason):
                                print(f"⚡ [PRE-MACRO DEFENSE] {symbol} at +{r_multiple:.2f}R approaching macro event! Banking profit & locking BE...")
                                self.execute_fleet_scaleout(symbol, entry, reason=f"Pre-Macro Defense: {cal_reason}")
                                sym_data["macro_scaleout_executed"] = True
                                self.alerted_trades[t_id]["macro_scaleout_executed"] = True
                                self.save_state()
                        except Exception as cal_err:
                            pass

                    # 7. Milestone Telegram Alerts (Deduplicated per Symbol)
                    for target in [1.5, 2.0, 2.5]:
                        target_key = str(target)
                        is_target_alerted = sym_data.get("milestones", {}).get(target_key) or self.alerted_trades.get(t_id, {}).get(target_key)
                        if r_multiple >= target and not is_target_alerted:
                            msg = (
                                f"🚀 <b>BAYESIAN PIVOT TARGET REACHED!</b>\n"
                                f"Symbol: <code>{symbol}</code>\n"
                                f"Current R: <b>{r_multiple:.2f}R</b>\n\n"
                                f"🛡️ <b>DISCIPLINE CHECK:</b> Target {target}R reached.\n"
                                f"Break-Even stop loss and autonomous protection active."
                            )
                            self.notifier._send_message(msg)
                            sym_data.setdefault("milestones", {})[target_key] = True
                            self.alerted_trades[t_id][target_key] = True
                            self.save_state()

            except Exception as e:
                print(f"Watchdog Loop Error: {e}")
            
            time.sleep(60) # Poll every 60s

    def execute_fleet_scaleout(self, symbol: str, entry_price: float, reason: str = "+1.5R Floating Gain Reached"):
        """
        Automated Fleet Scale-Out & Universal Break-Even Protection:
        - Trailing Stop Loss to Break-Even (entry price) across 100% of open positions on ALL active accounts.
        - Scale-out accounts (Account 1: idx 0, Account 3: idx 2, Account 9: idx 8) close Tranche 1 if multiple tranches open.
        - Pacing: 2.0s adaptive pacing between accounts (AGENTS.md Rule 5).
        """
        try:
            trailed_count = 0
            closed_count = 0
            target_sym = symbol.replace("/", "").replace("_", "").upper()
            
            # Decoupled fleet indices:
            # Scale-out accounts: Account 1 (0), Account 3 (2), Account 9 (8)
            # Runner accounts: Account 2 (1), Account 6 (5), Account 7 (6)
            # Decommissioned accounts: 3, 4, 7 (quarantined, zero risk)
            scale_out_indices = set(getattr(Config, 'SCALE_OUT_ACCOUNT_INDICES', [0, 2, 8]))

            for acc_idx, helper in enumerate(self.tl.helpers):
                if acc_idx > 0:
                    time.sleep(2.0) # Adaptive 2.0s pacing
                
                # Skip decommissioned liquidation-only accounts
                if getattr(helper, 'status', '') == 'LIQUIDATION_ONLY' or acc_idx in [3, 4, 7]:
                    continue

                if not helper.access_token and not helper.login():
                    continue

                try:
                    positions = helper.get_open_positions()
                    target_pos = [
                        p for p in positions 
                        if target_sym in str(p.get("symbol", "")).replace("/", "").replace("_", "").upper()
                    ]
                    
                    if not target_pos:
                        continue

                    is_mfe = "MFE Peak Retracement" in str(reason)
                    
                    if is_mfe:
                        # Defensive market closure: close ALL remaining positions on this account to lock in banked gain
                        for p in target_pos:
                            pid = p.get("id") or p.get("positionId")
                            if helper.close_position(pid):
                                closed_count += 1
                    elif acc_idx in scale_out_indices and len(target_pos) > 1:
                        # Close T1 (first tranche) to lock cash profit
                        t1_pos = target_pos[0]
                        pos_id = t1_pos.get("id") or t1_pos.get("positionId")
                        if helper.close_position(pos_id):
                            closed_count += 1
                        time.sleep(1.0)
                        # Update remaining position(s) to Break-Even
                        for p in target_pos[1:]:
                            pid = p.get("id") or p.get("positionId")
                            if helper.modify_position_bracket(pid, stop_loss=float(entry_price)):
                                trailed_count += 1
                    else:
                        # Trail all open positions on this account to Break-Even
                        for p in target_pos:
                            pid = p.get("id") or p.get("positionId")
                            if helper.modify_position_bracket(pid, stop_loss=float(entry_price)):
                                trailed_count += 1
                except Exception as acc_err:
                    print(f"Error scaling out account {acc_idx+1}: {acc_err}")

            if "MFE Peak Retracement" in str(reason):
                scaleout_msg = (
                    f"🛡️ <b>MFE PEAK RATCHET PROFIT LOCK</b>\n\n"
                    f"Symbol: <code>{symbol}</code>\n"
                    f"Trigger: <b>{reason}</b>\n\n"
                    f"🏦 <b>Realized Cash Profit:</b> Market-closed {closed_count} positions across fleet\n"
                    f"✅ <b>Invariant:</b> Protected peak profit. Zero surrender to reversal."
                )
            else:
                scaleout_msg = (
                    f"🛡️ <b>AUTONOMOUS FLEET PROFIT PROTECTION</b>\n\n"
                    f"Symbol: <code>{symbol}</code>\n"
                    f"Trigger: <b>{reason}</b>\n\n"
                    f"🔒 <b>Risk-Free Trailing:</b> Trailed Stop Loss to Entry (${entry_price:,.2f}) on {trailed_count} positions\n"
                    f"🏦 <b>Realized Cash Profit:</b> Closed {closed_count} tranches on scale-out accounts\n\n"
                    f"✅ <b>Invariant:</b> Zero risk remaining. Runners riding to full Target."
                )
            self.notifier._send_message(scaleout_msg)
            print(f"✅ Fleet Scale-Out Complete: Trailed={trailed_count}, Closed={closed_count}")
        except Exception as e:
            print(f"Error executing fleet scaleout: {e}")

if __name__ == "__main__":
    PositionWatchdog().run()
