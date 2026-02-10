import logging
import pandas as pd
from datetime import datetime, timedelta
from src.core.supabase_client import supabase
from src.clients.tl_client import TradeLockerClient
from ai_audit_engine import AIAuditEngine

logger = logging.getLogger(__name__)

class ExecutionAuditEngine:
    """
    The 'Policeman' of the system.
    Reconciles System Signals (Scans) with Real Executions (TradeLocker).
    """
    def __init__(self):
        self.tl = TradeLockerClient()
        self.sb = supabase
        self.ai = AIAuditEngine()
        
    def run_audit(self, hours_back=24):
        """
        Main Audit Loop:
        1. Fetch Signals from Supabase (Last N Hours)
        2. Fetch Executions from TradeLocker (Last N Hours)
        3. Match & Grade
        4. Update Journal
        """
        logger.info(f"👮‍♂️ Starting Execution Audit (Last {hours_back}h)...")
        
        # 1. Fetch Signals
        signals = self._fetch_recent_signals(hours_back)
        if not signals:
            logger.info("No high-quality signals found to audit.")
            return
            
        # 2. Fetch Executions (Closed History + Open Positions)
        # We need both because a signal might be currently active (Open) or already closed.
        history_trades = self.tl.get_recent_history(hours=hours_back)
        open_positions = self.tl.get_open_positions()
        
        # Normalize TL trades
        # We want a list of dicts: {symbol, side, entry_price, time, id, status, pnl}
        executions = []
        
        # Process History
        for t in history_trades:
            executions.append({
                "id": t['id'],
                "symbol": t['symbol'],
                "side": t['side'],
                "price": t['price'], # Close price for legacy, but we need entry. 
                # tl_client.get_recent_history unfortunately returns close price mostly.
                # We might need to fetch order history for exact entry.
                # For now, let's assume we can match by Time + Symbol.
                "time": t['close_time'], # Approximation
                "status": "CLOSED",
                "pnl": t['pnl']
            })
            
        # Process Open Positions
        # tl_client returns raw list or dict. verified_tl.py showed us raw list for Open.
        # open_positions from tl_client already normalizes this!
        executions.extend(open_positions)
        
        logger.info(f"Found {len(signals)} Signals vs {len(executions)} Executions.")
        
        # 3. Match & Grade
        for signal in signals:
            match = self._find_match(signal, executions)
            
            if match:
                self._grade_adherence(signal, match)
            else:
                self._mark_missed(signal)
                
        # 4. Check for Rogue Trades (Trades with NO Signal)
        for trade in executions:
            if not self._find_signal_for_trade(trade, signals):
                self._mark_rogue(trade)

    def _fetch_recent_signals(self, hours):
        """Fetches 'HIGH QUALITY' signals from Supabase scans table."""
        if not self.sb.client: return []
        
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        
        try:
            # We only care about signals that were 'PENDING' (Actionable)
            # and had a bias/pattern.
            resp = self.sb.client.table("scans")\
                .select("*")\
                .gt("timestamp", cutoff)\
                .execute()
                
            # Filter for High Quality locally if needed, or assume all logged scans are valid hints
            # For strictness, let's only audit logic that passed the AI check (ai_score > 7)
            valid_signals = [
                s for s in resp.data 
                if s.get('ai_score', 0) > 7.0 
            ]
            return valid_signals
        except Exception as e:
            logger.error(f"Failed to fetch signals: {e}")
            return []

    def _find_match(self, signal, executions):
        """
        Matching Logic:
        - Same Symbol
        - Same Side (Buy/Long vs Sell/Short)
        - Execution Time within 60 mins of Signal Time
        """
        # Parse Signal Time (Ensure Naive UTC)
        try:
            ts = signal['timestamp'].replace('Z', '')
            # Handle timezone offset responsibly
            if 'T' in ts:
                date_part, time_part = ts.split('T')
                if '+' in time_part: time_part = time_part.split('+')[0]
                if '-' in time_part: time_part = time_part.split('-')[0]
                ts = f"{date_part}T{time_part}"
            
            # Truncate microseconds if more than 6 digits or weird length
            if '.' in ts:
                base, micros = ts.split('.')
                micros = (micros + "000000")[:6] # Pad and truncate
                ts = f"{base}.{micros}"
                
            sig_time = datetime.fromisoformat(ts)
        except Exception as e:
            logger.error(f"Signal Timestamp Parse Error: {e} | {signal['timestamp']}")
            return None

        sig_symbol = signal['symbol'].replace("USDT", "USD") # Normalize
        sig_side = "BUY" if "Bullish" in signal.get('pattern', '') else "SELL"
        
        logger.info(f"🔎 AUDIT MATCHING: Signal {signal['id']} ({sig_symbol} {sig_side} @ {sig_time})")
        
        for trade in executions:
            # Normalize Trade Symbol
            trade_symbol = trade['symbol'].replace("USDT", "USD")
            
            # Side Check
            if trade['side'].upper() != sig_side: 
                # logger.debug(f"   Skip: Side Mismatch ({trade['side']} vs {sig_side})")
                continue
                
            # Symbol Check
            if trade_symbol != sig_symbol: 
                continue
            
            # Time Check (Handle different formats)
            try:
                t_val = trade.get('entry_time') or trade.get('time')
                if isinstance(t_val, str):
                    t_iso = t_val.replace('Z', '')
                    if 'T' in t_iso:
                        dp, tp = t_iso.split('T')
                        if '+' in tp: tp = tp.split('+')[0]
                        if '-' in tp: tp = tp.split('-')[0]
                        t_iso = f"{dp}T{tp}"
                    trade_time = datetime.fromisoformat(t_iso)
                elif isinstance(t_val, (int, float)):
                    # Millis
                    trade_time = datetime.utcfromtimestamp(t_val / 1000.0)
                else:
                    continue
                
                # Ensure validation against Naive UTC
                if trade_time.tzinfo:
                    trade_time = trade_time.replace(tzinfo=None)
                    
                delta = abs((trade_time - sig_time).total_seconds())
                logger.info(f"   Candidate: {trade['id']} Delta={delta}s")
                
                if delta < 3600: # 1 Hour Window
                    return trade
            except Exception as e:
                logger.error(f"Trade Time Parse Error: {e}")
                continue
                
        return None

    def _find_signal_for_trade(self, trade, signals):
        """Reverse lookup: Does this trade have a signal?"""
        # Same logic as _find_match but from trade's perspective
        for signal in signals:
            if self._find_match(signal, [trade]):
                return True
        return False 

    def _grade_adherence(self, signal, trade):
        """Updates Journal with Success"""
        logger.info(f"✅ ADHERENCE VERIFIED: Signal {signal['id']} -> Trade {trade['id']}")
        
        feedback = f"Disciplined Execution. Matched Signal: {signal['pattern']}"
        embedding = self.ai.get_text_embedding(feedback)
        
        # Log to Journal
        # We assume one journal entry per trade
        self.sb.log_journal_entry(
            trade_id=trade['id'],
            symbol=trade['symbol'],
            side=trade['side'],
            pnl=trade['pnl'],
            ai_grade=signal.get('ai_score', 0),
            mentor_feedback=feedback,
            strategy="SYSTEM",
            status=trade['status'],
            price=trade['price'],
            deviations="None",
            embedding=embedding
        )

    def _mark_missed(self, signal):
        """Logs a 'Missed Opportunity'"""
        logger.warning(f"❌ MISSED SIGNAL: {signal['symbol']} {signal['pattern']} at {signal['timestamp']}")
        # Potentially log to a 'missed_trades' table or journal with status 'MISSED'
        
    def _mark_rogue(self, trade):
        """Analyze a trade that had NO matching signal."""
        logger.info(f"🕵️‍♂️ Analyzing Discretionary Trade: {trade['symbol']} {trade['side']}")
        
        # Call AI to see if it's Alpha or Rogue
        audit = self.ai.audit_discretionary_trade(trade)
        
        strategy_label = "ALPHA" if audit.get('is_alpha', False) else "ROGUE"
        feedback = audit.get('feedback', 'No feedback provided.')
        embedding = self.ai.get_text_embedding(feedback)
        
        logger.info(f"   Result: {strategy_label} (Score: {audit.get('score')})")
        
        self.sb.log_journal_entry(
            trade_id=trade['id'],
            symbol=trade['symbol'],
            side=trade['side'],
            pnl=trade['pnl'],
            ai_grade=audit.get('score', 0.0),
            mentor_feedback=feedback,
            strategy=strategy_label,
            status=trade.get('status', 'CLOSED'),
            price=trade.get('price', 0.0),
            deviations=audit.get('improvement_suggestion', "Discretionary Entry"),
            embedding=embedding
        )
