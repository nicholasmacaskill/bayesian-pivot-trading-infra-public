import logging
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
from src.core.supabase_client import supabase
from src.clients.tl_client import TradeLockerClient
from src.engines.ai_audit_engine import AIAuditEngine
from src.engines.smc_scanner import SMCScanner

logger = logging.getLogger(__name__)

class ExecutionAuditEngine:
    """
    The 'Policeman' of the system.
    Reconciles System Signals (Scans) with Real Executions (TradeLocker).
    Also auto-contextualizes rogue (discretionary) trades for training data.
    """
    def __init__(self):
        self.tl = TradeLockerClient()
        self.sb = supabase
        self.ai = AIAuditEngine()
        self.scanner = SMCScanner()
        
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
        executions = []
        for t in history_trades:
            executions.append({
                "id": t['id'],
                "symbol": t['symbol'],
                "side": t['side'],
                "price": t['price'],
                "time": t['close_time'],
                "status": "CLOSED",
                "pnl": t['pnl']
            })
            
        executions.extend(open_positions)
        logger.info(f"Found {len(signals)} Signals vs {len(executions)} Executions.")
        
        # 3. Match & Grade
        for signal in signals:
            match = self._find_match(signal, executions)
            if match:
                self._grade_adherence(signal, match)
                # Rate-limit protection for Gemini
                time.sleep(2)
            else:
                self._mark_missed(signal)
                
        # 4. Check for Rogue Trades (Trades with NO Signal)
        for trade in executions:
            if not self._find_signal_for_trade(trade, signals):
                self._mark_rogue(trade)
                # Rate-limit protection for Gemini
                time.sleep(2)

    def _fetch_recent_signals(self, hours):
        """Fetches 'HIGH QUALITY' signals from Supabase scans table."""
        if not self.sb.client: return []
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        try:
            resp = self.sb.client.table("scans")\
                .select("*")\
                .gt("timestamp", cutoff)\
                .execute()
            return resp.data if resp.data else []
        except Exception as e:
            logger.error(f"Failed to fetch signals: {e}")
            return []

    def _find_match(self, signal, executions):
        """Matches a signal to an execution by symbol, side, and time proximity."""
        sig_time = datetime.fromisoformat(signal['timestamp'])
        for trade in executions:
            if trade['symbol'] == signal['symbol'] and trade['side'].upper() == signal['direction'].upper():
                # Allow 30 min window for entry execution
                trade_time_str = trade.get('time') or trade.get('entry_time')
                if not trade_time_str: continue
                # Handle varying ISO formats
                try:
                    trade_time = datetime.fromisoformat(trade_time_str.replace('Z', '+00:00'))
                except: continue
                
                diff = abs((trade_time - sig_time).total_seconds())
                if diff < 1800: # 30 mins
                    return trade
        return None

    def _find_signal_for_trade(self, trade, signals):
        """Inverse of _find_match: finds which signal spawned this trade."""
        trade_time_str = trade.get('time') or trade.get('entry_time')
        if not trade_time_str: return None
        try:
            trade_time = datetime.fromisoformat(trade_time_str.replace('Z', '+00:00'))
        except: return None

        for signal in signals:
            if signal['symbol'] == trade['symbol'] and signal['direction'].upper() == trade['side'].upper():
                sig_time = datetime.fromisoformat(signal['timestamp'])
                diff = abs((trade_time - sig_time).total_seconds())
                if diff < 1800:
                    return signal
        return None

    def _grade_adherence(self, signal, trade):
        """Uses AI Audit Engine to grade how well the trader followed the system signal."""
        logger.info(f"⚖️  Grading Adherence: {trade['symbol']} {trade['side']}")
        
        # Check if already graded
        existing = self.sb.client.table("journal").select("id").eq("trade_id", trade['id']).execute()
        if existing.data and len(existing.data) > 0:
            logger.info(f"   Trade {trade['id']} already graded. Skipping.")
            return

        # Prepare parameters for AI
        manual_trade = {
            "symbol": trade['symbol'],
            "side": trade['side'],
            "pnl": trade.get('pnl', 0.0),
            "timestamp": trade.get('time', 'Unknown'),
            "trade_id": trade['id']
        }
        system_data = {
            "patterns_found": signal['pattern'],
            "bias": signal.get('shadow_regime', 'Neutral')
        }
        
        audit = self.ai.audit_trade(manual_trade, system_data)
        
        # Log to Journal
        self.sb.log_journal_entry(
            trade_id=trade['id'],
            symbol=trade['symbol'],
            side=trade['side'],
            pnl=trade.get('pnl', 0.0),
            ai_grade=audit.get('score', 0.0),
            mentor_feedback=audit.get('feedback', ''),
            strategy="SYSTEM",
            status=trade['status'],
            price=trade.get('price', 0.0),
            deviations=" | ".join(audit.get('deviations', [])),
            notes=f"Signal Match: {signal['signal_id'] if 'signal_id' in signal else 'N/A'}"
        )

    def _mark_missed(self, signal):
        """Logs a signal that was generated but never taken by the trader."""
        # Check if already logged as missed
        # We don't want to spam the journal with the same missed signal every audit.
        # Use signal_id as a unique key in the journal's notes or as a separate check.
        pass

    def _mark_rogue(self, trade):
        """Auto-contextualizes a discretionary trade. Zero input required from trader."""
        logger.info(f"🕵️  Auto-Contextualizing Rogue Trade: {trade['symbol']} {trade['side']}")
        
        # Check if already logged
        existing = self.sb.client.table("journal").select("id").eq("trade_id", trade['id']).execute()
        if existing.data and len(existing.data) > 0:
            return

        ctx = self._reconstruct_market_context(trade)
        narrative = ctx.get('narrative', 'Discretionary trade — context unavailable')

        # Grade with AI using reconstructed context
        audit = self.ai.audit_discretionary_trade({**trade, 'auto_context': narrative})
        strategy_label = "ALPHA" if audit.get('is_alpha', False) else "ROGUE"

        # Embed the auto-generated narrative for semantic search
        embedding = self.ai.get_text_embedding(narrative)

        self.sb.log_journal_entry(
            trade_id=trade['id'],
            symbol=trade['symbol'],
            side=trade['side'],
            pnl=trade.get('pnl', 0.0),
            ai_grade=audit.get('score', 0.0),
            mentor_feedback=audit.get('feedback', narrative),
            strategy=strategy_label,
            status=trade.get('status', 'CLOSED'),
            price=trade.get('price', 0.0),
            deviations=narrative,
            notes=f"AUTO-CONTEXT | {ctx['session']} | {ctx['asian_context']}",
            embedding=embedding,
            timestamp=trade.get('entry_time') or trade.get('time')
        )
        logger.info(f"   ✅ Logged: {strategy_label} — '{narrative[:80]}...'")

    def _reconstruct_market_context(self, trade) -> dict:
        """
        Historical forensic reconstruction of the market state at the time of entry.
        Fetches 5m data around the trade timestamp to detect sweeps, SMT, and bias.
        """
        symbol = trade['symbol']
        side = trade['side']
        trade_time_str = trade.get('time') or trade.get('entry_time')
        
        # Default context
        ctx = {
            "session": "Unknown",
            "asian_context": "Unknown",
            "trend_bias": "Neutral",
            "liquidity_swept": "None detected",
            "price_quartile": "Middle",
            "narrative": f"Discretionary {side} trade on {symbol}."
        }
        
        if not trade_time_str: return ctx

        try:
            # 1. Fetch relevant window of data (12 hours before trade)
            trade_dt = datetime.fromisoformat(trade_time_str.replace('Z', '+00:00'))
            start_dt = trade_dt - timedelta(hours=12)
            
            # Fetch from scanner
            df = self.scanner.fetch_historical_data(symbol, timeframe='5m', limit=200) 
            # Note: tl_client.get_candles might be better for exact historical point,
            # but SMCScanner.fetch_... is already normalized.
            
            if df is None or df.empty: return ctx
            
            # Filter for data BEFORE the trade
            df_hist = df[df.index <= trade_dt].tail(100)
            if df_hist.empty: return ctx
            
            # 2. Forensic Analysis
            # A. Session
            hour = trade_dt.hour
            if 0 <= hour < 4: ctx['session'] = "ASIAN"
            elif 7 <= hour < 11: ctx['session'] = "LONDON"
            elif 12 <= hour < 17: ctx['session'] = "NY"
            else: ctx['session'] = "LATE_NY_RETRACEMENT"
            
            # B. Asian Range Position
            # Need to find the high/low of 00:00-04:00 today
            asian_start = trade_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            asian_end = trade_dt.replace(hour=4, minute=0, second=0, microsecond=0)
            asian_df = df[(df.index >= asian_start) & (df.index <= asian_end)]
            
            if not asian_df.empty:
                ah = asian_df['high'].max()
                al = asian_df['low'].min()
                price = trade['price'] or df_hist['close'].iloc[-1]
                
                if price > ah: ctx['asian_context'] = "Above Asian High (Premium)"
                elif price < al: ctx['asian_context'] = "Below Asian Low (Discount)"
                else: ctx['asian_context'] = "Inside Asian Range"
            
            # C. Institutional Footprint
            # Check for recent sweeps (wick beyond swing point + rejection)
            recent_swing_h = df_hist['high'].iloc[:-1].max()
            recent_swing_l = df_hist['low'].iloc[:-1].min()
            
            curr_h = df_hist['high'].iloc[-1]
            curr_l = df_hist['low'].iloc[-1]
            
            if side.upper() == 'BUY' and curr_l < recent_swing_l:
                ctx['liquidity_swept'] = "Internal Swing Low Swept"
            elif side.upper() == 'SELL' and curr_h > recent_swing_h:
                ctx['liquidity_swept'] = "Internal Swing High Swept"
                
            # D. Narrative Construction
            ctx['narrative'] = (
                f"Trade taken during {ctx['session']} session. "
                f"Price was {ctx['asian_context']}. "
                f"Institutional Flow: {ctx['liquidity_swept']}. "
                f"Trend context: {ctx['trend_bias']}."
            )
            
        except Exception as e:
            logger.error(f"Market reconstruction failed: {e}")
            
        return ctx
