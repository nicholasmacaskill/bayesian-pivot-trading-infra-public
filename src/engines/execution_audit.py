import logging
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from src.core.supabase_client import supabase
from src.clients.tl_client import TradeLockerClient
from ai_audit_engine import AIAuditEngine
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
            embedding=embedding,
            timestamp=trade.get('entry_time') or trade.get('time')
        )

    def _mark_missed(self, signal):
        """Logs a 'Missed Opportunity'"""
        logger.warning(f"❌ MISSED SIGNAL: {signal['symbol']} {signal['pattern']} at {signal['timestamp']}")

    # ─── Auto-Contextualizer Helpers ──────────────────────────────────────────

    def _infer_session(self, hour):
        """Maps UTC hour to trading session name."""
        if 4 <= hour < 7:   return "Asian Fade Window (PRIME)"
        if 7 <= hour < 10:  return "London Open"
        if 10 <= hour < 12: return "London Close"
        if 12 <= hour < 20: return "New York Session"
        if 0 <= hour < 4:   return "Asian Session"
        return "Off-Hours"

    def _get_entry_datetime(self, trade):
        """Safely parses trade entry time to naive UTC datetime."""
        t_val = trade.get('entry_time') or trade.get('time')
        try:
            if isinstance(t_val, (int, float)):
                return datetime.utcfromtimestamp(t_val / 1000.0)
            if isinstance(t_val, str):
                ts = t_val.replace('Z', '')
                if 'T' in ts:
                    dp, tp = ts.split('T')
                    tp = tp.split('+')[0].split('-')[0]
                    ts = f"{dp}T{tp}"
                return datetime.fromisoformat(ts)
        except Exception:
            pass
        return datetime.utcnow()

    def _reconstruct_market_context(self, trade):
        """
        AUTO-CONTEXTUALIZER: Reconstructs market state at the exact entry time.
        No input from trader required — uses historical 5m candle data.

        Infers:
            - Trading session (Asian Fade, London, NY, etc.)
            - Price position within Asian Range (Premium / Discount / Equilibrium)
            - 4H trend bias (EMA20 vs EMA50)
            - Whether a swing high/low was swept before entry
        """
        symbol = trade.get('symbol', 'BTC/USDT')
        entry_price = float(trade.get('price', 0))
        side = trade.get('side', 'SELL').upper()
        entry_dt = self._get_entry_datetime(trade)
        session = self._infer_session(entry_dt.hour)

        ctx = {
            'session': session,
            'price_quartile': 'Unknown',
            'trend_bias': 'Unknown',
            'asian_high': None,
            'asian_low': None,
            'asian_context': 'Unknown',
            'liquidity_swept': 'Unknown',
            'is_rogue': True,
        }

        try:
            # Fetch ~10h of 5m candles leading up to entry
            since_ms = int((entry_dt - timedelta(hours=10)).timestamp() * 1000)
            norm_symbol = symbol.replace('USD', 'USDT') if 'USDT' not in symbol else symbol
            ohlcv = self.scanner.exchange.fetch_ohlcv(norm_symbol, '5m', since=since_ms, limit=500)
            if not ohlcv:
                return ctx

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['hour'] = df['timestamp'].dt.hour

            # ── 1. Asian Range ────────────────────────────────────────────────
            asian_df = df[df['hour'].between(0, 3)].tail(48)
            if len(asian_df) >= 3:
                asian_high = asian_df['high'].max()
                asian_low  = asian_df['low'].min()
                asian_range = asian_high - asian_low
                ctx['asian_high'] = round(asian_high, 2)
                ctx['asian_low']  = round(asian_low, 2)

                if asian_range > 0:
                    pos = (entry_price - asian_low) / asian_range
                    if pos > 0.75:
                        ctx['price_quartile'] = 'Premium (Top 25%)'
                    elif pos < 0.25:
                        ctx['price_quartile'] = 'Discount (Bottom 25%)'
                    else:
                        ctx['price_quartile'] = 'Equilibrium'

                    if side == 'SELL' and entry_price >= asian_high * 0.998:
                        ctx['asian_context'] = f'Entry at Asian High — Classic Fade SHORT (H:{asian_high:,.0f})'
                    elif side == 'BUY' and entry_price <= asian_low * 1.002:
                        ctx['asian_context'] = f'Entry at Asian Low — Classic Fade LONG (L:{asian_low:,.0f})'
                    else:
                        ctx['asian_context'] = f'Inside Asian Range (H:{asian_high:,.0f} L:{asian_low:,.0f})'

            # ── 2. 4H Trend Bias ─────────────────────────────────────────────
            df_4h = self.scanner.fetch_data(symbol, '1h', limit=60)
            if df_4h is not None and len(df_4h) >= 50:
                ema20 = df_4h['close'].ewm(span=20).mean().iloc[-1]
                ema50 = df_4h['close'].ewm(span=50).mean().iloc[-1]
                if ema20 > ema50 * 1.001:
                    ctx['trend_bias'] = 'Bullish (EMA20 > EMA50)'
                elif ema20 < ema50 * 0.999:
                    ctx['trend_bias'] = 'Bearish (EMA20 < EMA50)'
                else:
                    ctx['trend_bias'] = 'Neutral (EMAs Converging)'

            # ── 3. Liquidity Sweep ───────────────────────────────────────────
            recent  = df.tail(12)  # Last 60 mins of 5m candles
            swing_h = df.tail(48)['high'].max()
            swing_l = df.tail(48)['low'].min()

            if side == 'SELL' and recent['high'].max() >= swing_h * 0.998:
                ctx['liquidity_swept'] = f'Swing High swept (${swing_h:,.0f})'
            elif side == 'BUY' and recent['low'].min() <= swing_l * 1.002:
                ctx['liquidity_swept'] = f'Swing Low swept (${swing_l:,.0f})'
            else:
                ctx['liquidity_swept'] = 'No obvious sweep'

        except Exception as e:
            logger.warning(f"Context reconstruction partial error ({symbol}): {e}")

        # ── Build Full Narrative ────────────────────────────────────────────
        direction = 'SHORT' if side == 'SELL' else 'LONG'
        ctx['narrative'] = (
            f"{symbol} {direction} | Session: {ctx['session']} | "
            f"Zone: {ctx['price_quartile']} | "
            f"4H Bias: {ctx['trend_bias']} | "
            f"Asian: {ctx['asian_context']} | "
            f"Liquidity: {ctx['liquidity_swept']}"
        )
        return ctx

    def _mark_rogue(self, trade):
        """Auto-contextualizes a discretionary trade. Zero input required from trader."""
        logger.info(f"🕵️  Auto-Contextualizing Rogue Trade: {trade['symbol']} {trade['side']}")

        ctx = self._reconstruct_market_context(trade)
        narrative = ctx.get('narrative', 'Discretionary trade — context unavailable')

        logger.info(f"   📍 Session:   {ctx['session']}")
        logger.info(f"   📊 Zone:      {ctx['price_quartile']}")
        logger.info(f"   📈 4H Bias:   {ctx['trend_bias']}")
        logger.info(f"   🏔  Asian:     {ctx['asian_context']}")
        logger.info(f"   💧 Liquidity: {ctx['liquidity_swept']}")

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
