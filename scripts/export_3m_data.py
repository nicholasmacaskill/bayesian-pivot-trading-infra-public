import os
import sys
import json
import sqlite3
from datetime import datetime, timezone, timedelta

# Add src to path
sys.path.append(os.getcwd())
from dotenv import load_dotenv
load_dotenv('.env')
load_dotenv('.env.local')

from src.clients.tl_client import TradeLockerClient

def export_data():
    print("🚀 Starting Enriched 3-Month Export Process (2026-05-14 to 2026-08-14)...")
    
    os.makedirs("exports", exist_ok=True)
    
    now_utc = datetime.now(timezone.utc)
    cutoff_90 = now_utc - timedelta(days=90)
    
    # ----------------------------------------------------
    # 1. EXTRACT TRADELOCKER TRADES
    # ----------------------------------------------------
    print("📥 [1/2] Harvesting TradeLocker Trades from API & Local Database...")
    
    tl = TradeLockerClient()
    tl_api_trades = []
    
    for i, h in enumerate(tl.helpers):
        if h.login():
            print(f"   Connected to Account {i+1}: {h.email}")
            history = h.get_recent_history(hours=2160) # 90 days
            for t in history:
                t['account'] = h.email
                tl_api_trades.append(t)
        else:
            print(f"   ⚠️ Could not login to Account {i+1}: {h.email}")

    conn = sqlite3.connect('data/smc_alpha.db')
    conn.row_factory = sqlite3.Row
    j_rows = conn.execute('SELECT * FROM journal').fetchall()
    
    seen_trade_ids = set()
    tradelocker_records = []
    
    # Process API trades first
    for t in tl_api_trades:
        tid = str(t.get('id'))
        if not tid or tid in seen_trade_ids:
            continue
            
        close_time_str = t.get('close_time', '')
        dt = None
        try:
            if close_time_str.endswith('Z'):
                dt = datetime.fromisoformat(close_time_str.replace('Z', '+00:00'))
            elif 'T' in close_time_str:
                dt = datetime.fromisoformat(close_time_str)
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
            
        if dt and dt < cutoff_90:
            continue
            
        seen_trade_ids.add(tid)
        tradelocker_records.append({
            "trade_id": tid,
            "account": t.get('account', 'TradeLocker API'),
            "symbol": t.get('symbol', 'N/A'),
            "side": t.get('side', 'N/A'),
            "qty": t.get('qty', 0.0),
            "entry_price": t.get('entry_price', 0.0),
            "close_price": t.get('price', 0.0),
            "pnl": round(float(t.get('pnl', 0.0)), 2),
            "close_time": close_time_str,
            "status": t.get('status', 'CLOSED')
        })
        
    # Merge DB Journal trades
    for r in j_rows:
        tid = str(r['trade_id'])
        if not tid or tid in seen_trade_ids:
            continue
            
        ts_str = str(r['timestamp'])
        dt = None
        try:
            if ts_str.isdigit():
                val = float(ts_str)
                if val > 1e11: val /= 1000.0
                dt = datetime.fromtimestamp(val, tz=timezone.utc)
            elif ts_str.endswith('Z'):
                dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            elif 'T' in ts_str:
                dt = datetime.fromisoformat(ts_str)
                if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
            
        if dt and dt < cutoff_90:
            continue
            
        seen_trade_ids.add(tid)
        tradelocker_records.append({
            "trade_id": tid,
            "account": "System Journal",
            "symbol": r['symbol'],
            "side": r['side'],
            "qty": "N/A",
            "entry_price": "N/A",
            "close_price": r['price'],
            "pnl": round(float(r['pnl']), 2) if r['pnl'] is not None else 0.0,
            "close_time": dt.isoformat() if dt else ts_str,
            "status": r['status']
        })
        
    tradelocker_records.sort(key=lambda x: x['close_time'], reverse=True)
    print(f"✅ Extracted {len(tradelocker_records)} total unique TradeLocker trades for the last 3 months.")

    # Write TradeLocker output files
    tl_file_txt = "exports/tradelocker_trades_3months.txt"
    tl_file_csv = "exports/tradelocker_trades_3months.csv"
    
    with open(tl_file_txt, "w", encoding="utf-8") as f:
        f.write("# TRADELOCKER TRADES LOG — LAST 3 MONTHS (MAY 14, 2026 - AUG 14, 2026)\n")
        f.write(f"# Total Records: {len(tradelocker_records)}\n")
        f.write("# Format: Tabular Text / Markdown & JSON Copy-Paste Ready\n\n")
        f.write("| Trade ID | Account | Timestamp (UTC) | Symbol | Side | Qty/Lots | Entry Price | Close Price | Realized PnL ($) | Status |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for rec in tradelocker_records:
            f.write(f"| {rec['trade_id']} | {rec['account']} | {rec['close_time']} | {rec['symbol']} | {rec['side']} | {rec['qty']} | {rec['entry_price']} | {rec['close_price']} | ${rec['pnl']} | {rec['status']} |\n")
            
        f.write("\n\n" + "="*80 + "\n")
        f.write("RAW JSON RECORD BLOCK (COPY & PASTE READY)\n")
        f.write("="*80 + "\n")
        f.write(json.dumps(tradelocker_records, indent=2))
        
    with open(tl_file_csv, "w", encoding="utf-8") as f:
        f.write("Trade ID,Account,Timestamp (UTC),Symbol,Side,Qty/Lots,Entry Price,Close Price,Realized PnL ($),Status\n")
        for rec in tradelocker_records:
            f.write(f'"{rec["trade_id"]}","{rec["account"]}","{rec["close_time"]}","{rec["symbol"]}","{rec["side"]}","{rec["qty"]}","{rec["entry_price"]}","{rec["close_price"]}",{rec["pnl"]},"{rec["status"]}"\n')

    # ----------------------------------------------------
    # 2. EXTRACT TELEGRAM SCANNER CALLS (ENRICHED)
    # ----------------------------------------------------
    print("📥 [2/2] Harvesting Telegram Scanner Calls with Full Call Explanations...")
    
    sl_rows = conn.execute('SELECT * FROM signed_ledger ORDER BY timestamp DESC').fetchall()
    scan_rows = conn.execute('SELECT * FROM scans WHERE ai_score >= 7.5 AND verdict IN ("ACCEPTED", "CONFIRMED") ORDER BY timestamp DESC').fetchall()
    
    seen_signatures = set()
    telegram_calls = []
    
    # 2a. Process Cryptographically Signed Ledger Records
    for r in sl_rows:
        ts_str = str(r['timestamp'])
        dt = None
        try:
            if 'T' in ts_str:
                dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
            else:
                dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
            
        if dt and dt < cutoff_90:
            continue
            
        sig = r['signature']
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)
        
        call_action = f"SIGNAL: {r['direction']} {r['symbol']}"
        call_summary = f"{r['direction']} call on {r['symbol']} via {r['pattern']} (AI Score: {r['ai_score']}/10). Entry: {r['entry_price']}, SL: {r['stop_loss']}, TP: {r['take_profit']}"
        
        telegram_calls.append({
            "signal_id": r['signal_id'],
            "timestamp": r['timestamp'],
            "call_action": call_action,
            "symbol": r['symbol'],
            "direction": r['direction'],
            "pattern": r['pattern'],
            "ai_score": r['ai_score'],
            "entry_price": r['entry_price'],
            "stop_loss": r['stop_loss'],
            "take_profit": r['take_profit'],
            "call_summary": call_summary,
            "ai_reasoning": r['notes'] or f"Signed trade signal executed by Sovereign Engine with RSA key signature.",
            "shadow_regime": r['shadow_regime'],
            "outcome": r['outcome'],
            "trade_id": r['trade_id'],
            "payload_hash": r['payload_hash'],
            "signature": r['signature'],
            "type": "CRYPTOGRAPHICALLY_SIGNED_ALERT"
        })

    # 2b. Process High Confidence Scanner Signals (Scans table)
    for r in scan_rows:
        ts_str = str(r['timestamp'])
        dt = None
        try:
            if 'T' in ts_str:
                dt = datetime.fromisoformat(ts_str)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
        except Exception:
            pass
            
        if dt and dt < cutoff_90:
            continue
            
        is_dup = False
        for c in telegram_calls:
            if c['symbol'] == r['symbol'] and c['direction'] == r['direction']:
                c_ts = c['timestamp']
                try:
                    c_dt = datetime.fromisoformat(c_ts.replace('Z', '+00:00')) if 'T' in c_ts else datetime.fromisoformat(c_ts)
                    if c_dt.tzinfo is None: c_dt = c_dt.replace(tzinfo=timezone.utc)
                    if dt and abs((dt - c_dt).total_seconds()) < 10:
                        is_dup = True
                        break
                except Exception:
                    pass
        if is_dup:
            continue
            
        call_action = f"CALL: {r['direction']} {r['symbol']}"
        call_summary = f"{r['direction']} alert on {r['symbol']} via {r['pattern']} (AI Score: {r['ai_score']}/10, Session: {r['session']}, Regime: {r['shadow_regime']})"
        
        telegram_calls.append({
            "signal_id": f"SCAN-ID-{r['id']}",
            "timestamp": r['timestamp'],
            "call_action": call_action,
            "symbol": r['symbol'],
            "direction": r['direction'],
            "pattern": r['pattern'],
            "ai_score": r['ai_score'],
            "entry_price": "N/A",
            "stop_loss": "N/A",
            "take_profit": "N/A",
            "call_summary": call_summary,
            "ai_reasoning": r['ai_reasoning'] or "Scanner identified high probability structural confluence.",
            "session": r['session'],
            "shadow_regime": r['shadow_regime'],
            "outcome": r['verdict'],
            "trade_id": "N/A",
            "payload_hash": "N/A",
            "signature": "SCANNER_CONFIRMED_ALERT",
            "type": "SCANNER_HIGH_CONFIDENCE_ALERT"
        })

    telegram_calls.sort(key=lambda x: str(x['timestamp']), reverse=True)
    print(f"✅ Extracted {len(telegram_calls)} enriched Telegram scanner calls for the last 3 months.")

    # Write Enriched Telegram Scanner Calls output files
    tg_file_txt = "exports/telegram_scanner_calls_3months.txt"
    tg_file_csv = "exports/telegram_scanner_calls_3months.csv"
    
    with open(tg_file_txt, "w", encoding="utf-8") as f:
        f.write("# TELEGRAM SCANNER CALLS LOG — LAST 3 MONTHS (MAY 14, 2026 - AUG 14, 2026)\n")
        f.write(f"# Total Records: {len(telegram_calls)}\n")
        f.write("# Format: Enriched Tabular Text / Markdown & JSON Copy-Paste Ready\n\n")
        f.write("| Signal ID | Timestamp (UTC) | Call Action | Symbol | Direction | Pattern | AI Score | Entry | SL | TP | Call Summary |\n")
        f.write("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |\n")
        for rec in telegram_calls:
            f.write(f"| {rec['signal_id']} | {rec['timestamp']} | **{rec['call_action']}** | {rec['symbol']} | {rec['direction']} | {rec['pattern']} | {rec['ai_score']} | {rec['entry_price']} | {rec['stop_loss']} | {rec['take_profit']} | {rec['call_summary']} |\n")
            
        f.write("\n\n" + "="*80 + "\n")
        f.write("RAW ENRICHED JSON RECORD BLOCK (INCLUDES FULL AI REASONING & SETUP META)\n")
        f.write("="*80 + "\n")
        f.write(json.dumps(telegram_calls, indent=2))
        
    with open(tg_file_csv, "w", encoding="utf-8") as f:
        f.write("Signal ID,Timestamp (UTC),Call Action,Symbol,Direction,Pattern,AI Score,Entry Price,Stop Loss,Take Profit,Call Summary,AI Reasoning\n")
        for rec in telegram_calls:
            reasoning_clean = str(rec.get('ai_reasoning', '')).replace('"', '""')
            summary_clean = str(rec.get('call_summary', '')).replace('"', '""')
            f.write(f'"{rec["signal_id"]}","{rec["timestamp"]}","{rec["call_action"]}","{rec["symbol"]}","{rec["direction"]}","{rec["pattern"]}",{rec["ai_score"]},"{rec["entry_price"]}","{rec["stop_loss"]}","{rec["take_profit"]}","{summary_clean}","{reasoning_clean}"\n')

    print(f"\n🎉 EXPORT COMPLETE!")
    print(f"📄 TradeLocker Trades File: {tl_file_txt} ({os.path.getsize(tl_file_txt)} bytes)")
    print(f"📄 Telegram Calls File: {tg_file_txt} ({os.path.getsize(tg_file_txt)} bytes)")

if __name__ == "__main__":
    export_data()
