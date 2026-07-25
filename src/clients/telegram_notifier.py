from __future__ import annotations
import json
import logging
import requests
import os
from datetime import datetime

logger = logging.getLogger(__name__)

def _format_time_ago(minutes):
    if not isinstance(minutes, (int, float)) or minutes < 0:
        return "?"
    days = int(minutes // 1440)
    hours = int((minutes % 1440) // 60)
    mins = int(minutes % 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins or not parts:
        parts.append(f"{mins}m")
    return " ".join(parts) + " ago"


class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id   = chat_id   or os.environ.get("TELEGRAM_CHAT_ID")
        self.base_url  = f"https://api.telegram.org/bot{self.bot_token}"
        logger.info(f"📤 Notifier Initialized | Chat ID: {self.chat_id}")

        self.last_alerts    = {}   # deduplication tracker
        self.COOLDOWN_MINUTES = 60

    # ──────────────────────────────────────────────────────────────────────────
    # V3 SOVEREIGN ALERT
    # ──────────────────────────────────────────────────────────────────────────

    def send_alert(self, symbol, timeframe, pattern, ai_score, reasoning,
                   verdict="N/A", risk_calc=None, buttons=None,
                   regime_result=None,
                   health_report=None,
                   bias_data=None,
                   liquidity_targets=None,
                   session_info=None,
                   shadow_insights=None,
                   security_status=None,
                   psych_data=None,
                   direction=None):
        """V3 Hierarchy of Edge alert — strict HTML, mobile-first, agent-readable."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not set. Skipping alert.")
            return

        # ── Deduplication ────────────────────────────────────────────────────
        now      = datetime.now()
        alert_key = f"{symbol}_{pattern}"
        if alert_key in self.last_alerts:
            elapsed = (now - self.last_alerts[alert_key]).total_seconds() / 60
            if elapsed < self.COOLDOWN_MINUTES:
                logger.info(f"🤫 Suppressing duplicate {symbol} ({elapsed:.0f}m ago)")
                return
        self.last_alerts[alert_key] = now

        # ── 1. HEADER ─────────────────────────────────────────────────────────
        hr          = health_report or {}
        dd_pct      = hr.get('daily_drawdown', 0.0) * 100
        equity_buf  = hr.get('equity_buffer_usd', 0.0)
        sess_phase  = session_info.get('phase', 'Unknown') if session_info else 'Unknown'
        kz_name     = session_info.get('name', 'OFF-HOURS') if session_info else 'OFF-HOURS'

        badge = '⚠️ [WARNING]' if dd_pct >= 3.0 else '🛡️ [SECURE]'
        header = (
            f"{badge} | 🏁 <b>{kz_name} — {sess_phase}</b> | "
            f"📉 Buffer: <code>${equity_buf:,.0f}</code>"
        )

        # ── 2. BIAS CONFLUENCE ────────────────────────────────────────────────
        bd  = bias_data or {}
        confluence = (
            f"📐 <b>BIAS CONFLUENCE</b>\n"
            f"• Daily: <code>{bd.get('daily','N/A')}</code> | "
            f"HTF: <code>{bd.get('htf','N/A')}</code> | "
            f"Intermarket: <code>{bd.get('dxy_trend','N/A')}</code>"
        )

        # ── 3. LIQUIDITY EDGE ─────────────────────────────────────────────────
        lt = liquidity_targets or {}
        draw_px   = lt.get('target_price', 'N/A')
        draw_type = lt.get('target_type', 'N/A')
        dist_pips = lt.get('distance_pips', 'N/A')
        if isinstance(draw_px, float):   draw_px   = f"{draw_px:,.4f}"
        if isinstance(dist_pips, float): dist_pips = f"{dist_pips:.1f}"
        liquidity = (
            f"🎯 <b>LIQUIDITY EDGE</b>\n"
            f"• Draw on Liquidity: <code>{draw_px}</code> <i>({draw_type})</i>\n"
            f"• Gravity: <code>{dist_pips} pips</code>"
        )

        # ── 4. THE HUNT ───────────────────────────────────────────────────────
        hunt = (
            f"🦅 <b>THE HUNT</b>\n"
            f"• Active Strategy: <code>{pattern}</code> (<b>{ai_score}/10</b>)\n"
            f"• Hunt Logic: <i>{reasoning}</i>"
        )

        # ── 5. SYSTEM STATE ───────────────────────────────────────────────────
        pd          = psych_data or {}
        mood        = pd.get('mood', 'N/A')
        alpha_mult  = regime_result.suggested_size_mult if regime_result and hasattr(regime_result, 'suggested_size_mult') else 'N/A'
        atr_pct_ile = regime_result.atr_percentile      if regime_result and hasattr(regime_result, 'atr_percentile')      else 'N/A'
        slip        = (shadow_insights or {}).get('slippage_estimate', 'N/A')

        if isinstance(alpha_mult, float): alpha_mult = f"{alpha_mult:.2f}"

        system_state = (
            f"🔬 <b>SYSTEM STATE</b>\n"
            f"• Mood: <code>{mood}</code> | Alpha Persistence: <code>{alpha_mult}x</code>\n"
            f"• Volatility: <code>{atr_pct_ile}th %ile</code> | Slip: <code>{slip}</code>"
        )

        # ── 6. EXECUTION ──────────────────────────────────────────────────────
        exec_block = ""
        if risk_calc:
            entry = risk_calc.get('entry', 0)
            sl    = risk_calc.get('stop_loss', 0)
            lots  = risk_calc.get('position_size', 0)
            pos_val = risk_calc.get('position_value', 0)
            tp    = risk_calc.get('take_profit', 'OPEN')
            tp_str = f"${tp:,.4f}" if isinstance(tp, (int, float)) else str(tp)
            
            val_str = f" | Position Value: <code>${pos_val:,.2f}</code>" if pos_val > 0 else ""
            
            exec_block = (
                f"\n💷 <b>EXECUTION</b>\n"
                f"• Entry: <code>${entry:,.4f}</code> | SL: <code>${sl:,.4f}</code> | TP: <code>{tp_str}</code>\n"
                f"• Position Size: <code>{lots}</code>{val_str}"
            )

        # ── 7. AGENT-READABLE JSON SPOILER ────────────────────────────────────
        agent_payload = {
            "symbol":  symbol,
            "regime":  regime_result.regime.value if regime_result and hasattr(regime_result, 'regime') else None,
            "bias":    {"daily": bd.get('daily'), "htf": bd.get('htf'), "dxy": bd.get('dxy_trend')},
            "draw":    {"price": lt.get('target_price'), "type": lt.get('target_type'), "pips": lt.get('distance_pips')},
            "risk":    {"size_mult": regime_result.suggested_size_mult if regime_result and hasattr(regime_result, 'suggested_size_mult') else None,
                        "dd_pct": round(dd_pct, 2), "buffer_usd": equity_buf},
        }
        spoiler_block = (
            f"\n\n<tg-spoiler>agent_data: {json.dumps(agent_payload, default=str)}</tg-spoiler>"
        )

        # ── TradingView Link ──────────────────────────────────────────────────
        tv_sym  = symbol.replace("/", "")
        tv_link = f"https://www.tradingview.com/chart/?symbol=BINANCE:{tv_sym}"
        # Derive direction from the explicit signal direction first; fall back to
        # case-insensitive pattern matching so labels like "FVG_BULLISH" are handled.
        dir_upper = (direction or "").upper()
        is_long = (
            dir_upper == "LONG"
            or "LONG" in (pattern or "").upper()
            or "BULLISH" in (pattern or "").upper()
        )
        emoji   = "🟢" if is_long else "🔴"
        grade   = "🦄 UNICORN" if ai_score >= 8.5 else ("🦅 HIGH ALPHA" if ai_score >= 7.5 else "⚠️ MED ALPHA")

        # ── ASSEMBLE ──────────────────────────────────────────────────────────
        warning_block = ""
        if is_long:
            warning_block = (
                f"\n\n⚠️ <b>HISTORICAL RISK ALERT:</b> Long trades represent your largest manual draw. "
                f"Ensure strict limit execution and 50% risk reduction ($50 USD max risk)."
            )
        
        if (bias_data or {}).get('bias_conflict'):
            conflict_warning = (
                f"\n\n⚠️ <b>BIAS CONFLICT:</b> Multi-timeframe bias is conflicted (1D vs 4H/1H divergence). "
                f"Trade size reduced to 50% of normal. Monitor closely for structural break."
            )
            warning_block = (warning_block or "") + conflict_warning

        msg = (
            f"{emoji} <b>{grade}: {symbol}</b>\n"
            f"{header}\n\n"
            f"{hunt}\n\n"
            f"{confluence}\n\n"
            f"{liquidity}\n\n"
            f"{system_state}"
            f"{exec_block}"
            f"{warning_block}\n\n"
            f"📊 <a href='{tv_link}'>View on TradingView</a>"
            f"{spoiler_block}"
        )
        self._send_message(msg, buttons=buttons)

    # ──────────────────────────────────────────────────────────────────────────
    # V3 /scan BRIEFING
    # ──────────────────────────────────────────────────────────────────────────

    def send_scan_briefing(self, header_data: dict, account_data: dict,
                           performance_data: dict, confluence_data: dict,
                           market_rows: list, latest_setup: dict | None,
                           latest_rejected: dict | None = None,
                           strategic_directive: str | None = None):
        """
        Sends the full V3 Sovereign Briefing on /scan command.
        All ASCII tables are replaced with HTML lists for mobile readability.
        """
        # ── HEADER ────────────────────────────────────────────────────────────
        badge      = '⚠️ <b>[INTEGRITY: WARNING]</b>' if header_data.get('dd_pct', 0) >= 3.0 else '🛡️ <b>[INTEGRITY: SECURE]</b>'
        trust      = header_data.get('trust', 100)
        kz_name    = header_data.get('kz_name', 'OFF-HOURS')
        sess_phase = header_data.get('sess_phase', 'Unknown')
        dd_pct     = header_data.get('dd_pct', 0.0)
        buf_usd    = header_data.get('equity_buffer_usd', 0.0)
        uptime     = header_data.get('uptime', 'N/A')
        cycle      = header_data.get('cycle', 0)
        security   = header_data.get('security', 'N/A')

        header = (
            f"🔍 <b>BAYESIAN PIVOT BRIEFING v3</b>\n"
            f"{badge} | Trust: <code>{trust}/100</code>\n"
            f"🏁 <b>{kz_name}</b> — {sess_phase}\n"
            f"📉 DD: <code>{dd_pct:.1f}%</code> | Buffer: <code>${buf_usd:,.0f}</code>\n"
            f"🕒 Uptime: <code>{uptime}</code> | Cycle <code>#{cycle}</code>\n"
            f"🔐 <code>{security}</code>"
        )

        # ── ACCOUNT ───────────────────────────────────────────────────────────
        equity    = account_data.get('equity', 0)
        acct_block = f"💰 <b>Account</b>\n• Equity: <code>${equity:,.2f}</code>"

        # ── OPEN POSITIONS ────────────────────────────────────────────────────
        positions = account_data.get('positions', [])
        if positions:
            pos_lines = []
            for p in positions:
                pnl  = p.get('pnl', 0)
                icon = '🟢' if pnl >= 0 else '🔴'
                side = 'BUY' if p.get('side','').upper() == 'BUY' else 'SELL'
                pos_lines.append(f"  {icon} <code>{p.get('symbol','N/A')}</code> {side} @ <code>{p.get('price',0):.4f}</code> → <code>{pnl:+.2f}</code>")
            pos_block = f"📂 <b>Open ({len(positions)})</b>\n" + "\n".join(pos_lines)
        else:
            pos_block = "📂 <b>Open Positions</b>\n  <i>None</i>"

        # ── PERFORMANCE ───────────────────────────────────────────────────────
        n_trades  = performance_data.get('total_trades', 0)
        win_rate  = performance_data.get('win_rate', 0)
        avg_rr    = performance_data.get('avg_rr', 0)
        avg_win   = performance_data.get('avg_win', 0)
        avg_loss  = performance_data.get('avg_loss', 0)
        recent    = performance_data.get('recent', [])

        perf_block = (
            f"📈 <b>Performance ({n_trades} trades)</b>\n"
            f"• Win Rate: <code>{win_rate:.1f}%</code> | Avg RR: <code>{avg_rr:.2f}</code>\n"
            f"• Avg Win: <code>${avg_win:+.2f}</code> | Avg Loss: <code>-${avg_loss:.2f}</code>"
        )
        if recent:
            perf_block += "\n\n🕔 <b>Last 5 Closed</b>"
            for t in recent:
                pnl  = t.get('pnl', 0)
                icon = '🟢' if pnl >= 0 else '🔴'
                ts   = t.get('close_time', '')[:10]
                perf_block += f"\n  {icon} <code>{t.get('symbol','?')}</code> {t.get('side','')} {ts} → <code>{pnl:+.2f}</code>"

        # ── BIAS CONFLUENCE ───────────────────────────────────────────────────
        dxy = confluence_data.get('dxy', {})
        nq  = confluence_data.get('nq', {})
        tnx = confluence_data.get('tnx', {})
        alpha_mult      = confluence_data.get('alpha_mult', 1.0)
        alpha_reasoning = confluence_data.get('alpha_reasoning', 'N/A')

        confluence_block = (
            f"📐 <b>Confluence (Intermarket)</b>\n"
            f"• DXY: <code>{dxy.get('trend','N/A')}</code> (<code>{dxy.get('change_ltf',0):+.2f}%</code>)\n"
            f"• NQ: <code>{nq.get('trend','N/A')}</code> (<code>{nq.get('change_ltf',0):+.2f}%</code>)\n"
            f"• TNX: <code>{tnx.get('trend','N/A')}</code> (<code>{tnx.get('change_ltf',0):+.2f}%</code>)\n"
            f"✨ Alpha: <code>{alpha_mult:.2f}x</code> — <i>{alpha_reasoning}</i>"
        )

        # ── MARKET STATE (HTML list, no ASCII table) ──────────────────────────
        if market_rows:
            market_block = "📊 <b>Market State</b>\n"
            for row in market_rows:
                sym    = row.get('symbol','?').split('/')[0]
                bias   = row.get('bias','N/A')
                regime = row.get('regime','N/A')
                h      = row.get('hurst', 0.5)
                strat  = 'Turtle Soup' if h < 0.45 else ('Trend Align' if h > 0.55 else 'Structure')
                draw   = row.get('draw', None)
                draw_str = f" | Draw: <code>{draw}</code>" if draw else ""
                market_block += f"• <b>{sym}</b> — <code>{bias}</code> | {regime} | H:{h:.2f} [{strat}]{draw_str}\n"
        else:
            market_block = "📊 <b>Market State</b>\n<i>No scan data yet.</i>"

        # ── LATEST SETUPS (Call vs Rejected) ──────────────────────────────────
        setup_block = ''
        if latest_setup:
            mins_ago = latest_setup.get('mins_ago', '?')
            setup_block += (
                f"💎 <b>Latest Call</b>: <code>{latest_setup.get('symbol','?')}</code> ({_format_time_ago(mins_ago)})\n"
                f"  • Formation: <code>{latest_setup.get('pattern','N/A')}</code> | AI: <b>{latest_setup.get('ai_score','N/A')}/10</b>\n"
            )
        
        if latest_rejected:
            mins_ago_rej = latest_rejected.get('mins_ago', '?')
            if setup_block: setup_block += "\n"
            setup_block += (
                f"❌ <b>Latest Rejected</b>: <code>{latest_rejected.get('symbol','?')}</code> ({_format_time_ago(mins_ago_rej)})\n"
                f"  • Formation: <code>{latest_rejected.get('pattern','N/A')}</code> | AI: <code>{latest_rejected.get('ai_score','N/A')}/10</code>\n"
            )

        if not setup_block:
            setup_block = "🔭 <b>Setups Today</b>\n  <i>No signals detected this session.</i>"

        # ── STRATEGIC DIRECTIVE ───────────────────────────────────────────────
        directive_block = ""
        if strategic_directive:
            directive_block = f"🧠 <b>Strategic Directive</b>\n• {strategic_directive}"

        # ── AGENT SPOILER ─────────────────────────────────────────────────────
        agent_payload = {
            "equity": equity,
            "dd_pct": dd_pct,
            "buffer_usd": buf_usd,
            "win_rate": win_rate,
            "avg_rr": avg_rr,
            "dxy": dxy.get('trend'),
            "kz": kz_name,
            "sess_phase": sess_phase,
            "market": [{"sym": r.get('symbol','').split('/')[0], "bias": r.get('bias'), "hurst": r.get('hurst')} for r in market_rows],
        }
        spoiler = f"\n<tg-spoiler>agent_data: {json.dumps(agent_payload, default=str)}</tg-spoiler>"

        # ── ASSEMBLE ──────────────────────────────────────────────────────────
        msg = f"{header}\n\n"
        if directive_block:
            msg += f"{directive_block}\n\n"
        msg += (
            f"{acct_block}\n\n"
            f"{pos_block}\n\n"
            f"{perf_block}\n\n"
            f"{confluence_block}\n\n"
            f"{market_block}\n"
            f"{setup_block}"
            f"{spoiler}"
        )
        self._send_message(msg)

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def send_security_alert(self, title: str, summary: str, severity: str = "HIGH"):
        icon = {"CRITICAL": "🚨", "HIGH": "⚠️", "MEDIUM": "🟡"}.get(severity, "⚠️")
        msg = (
            f"{icon} <b>BAYESIAN PIVOT GUARD — {severity}</b>\n\n"
            f"🛡️ <b>{title}</b>\n\n{summary}\n\n"
            f"⏰ <code>{datetime.now().strftime('%H:%M:%S UTC')}</code>"
        )
        self._send_message(msg)

    def send_kill_switch(self, reason):
        self._send_message(
            f"⚠️ <b>CIRCUIT BREAKER TRIGGERED</b>\n\n"
            f"🛑 Reason: {reason}\n\n"
            f"Trading suspended until manual reset or 00:00 UTC."
        )

    def send_system_error(self, component, error):
        self._send_message(
            f"🆘 <b>CRITICAL ERROR</b>\n\n"
            f"📍 Component: <code>{component}</code>\n"
            f"❌ Error: <code>{str(error)[:300]}</code>\n\n"
            f"Check local logs for details."
        )

    def _send_message(self, text, buttons=None):
        if not self.bot_token or not self.chat_id:
            return
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            r = requests.post(f"{self.base_url}/sendMessage", json=payload, timeout=5)
            logger.info(f"📤 TG ({r.status_code}): {r.text[:80]}")
            r.raise_for_status()
        except Exception as e:
            logger.error(f"❌ Telegram send failed: {e}")

    def get_latest_message(self, since_timestamp=None):
        try:
            r = requests.get(f"{self.base_url}/getUpdates",
                             params={"limit": 100, "allowed_updates": ["message"]}, timeout=5)
            r.raise_for_status()
            msgs = []
            for upd in r.json().get("result", []):
                msg = upd.get("message")
                if not msg or str(msg.get("chat", {}).get("id")) != str(self.chat_id):
                    continue
                txt = msg.get("text")
                ts  = msg.get("date")
                if txt and (not since_timestamp or ts > since_timestamp):
                    msgs.append({"text": txt, "timestamp": ts})
            return sorted(msgs, key=lambda x: x["timestamp"])[-1] if msgs else None
        except Exception as e:
            logger.error(f"TG getUpdates failed: {e}")
            return None

    def send_photo(self, photo_path, caption=None):
        try:
            with open(photo_path, 'rb') as f:
                payload = {'chat_id': self.chat_id}
                if caption:
                    payload.update({'caption': caption, 'parse_mode': 'HTML'})
                requests.post(f"{self.base_url}/sendPhoto",
                              data=payload, files={'photo': f}, timeout=10)
        except Exception as e:
            logger.error(f"TG photo failed: {e}")


    def send_high_confluence_alert(self, symbol: str, direction: str, entry: float,
                                   stop_loss: float, target: float, ai_score: float,
                                   smt_strength: float, session_name: str,
                                   price_quartile: float, buttons: list = None):
        """
        Pushes an elite Golden Confluence Payout Alert when a setup passes all 5 rigid edge criteria:
          1. NY AM Session (07:00-10:00 EST)
          2. SMT Strength >= 0.50
          3. Q2 Manipulation Window
          4. Deep Discount (<0.25) or Deep Premium (>0.75)
          5. AI Validator Score >= 8.5
        """
        is_long = direction.upper() == "LONG"
        emoji = "🟢" if is_long else "🔴"
        risk_dist = abs(entry - stop_loss)
        reward_dist = abs(target - entry)
        rr = reward_dist / risk_dist if risk_dist > 0 else 2.5
        target_pnl = 150.0 * rr  # Estimated PnL at standard $150 risk

        msg = (
            f"🏆 <b>GOLDEN CONFLUENCE ALERT (PAYOUT PLAY)</b>\n"
            f"{emoji} <b>{symbol} {direction.upper()} @ ${entry:,.2f}</b>\n"
            f"🤖 <b>AI Score: {ai_score}/10 (FLOW_GO)</b>\n\n"
            f"🔥 <b>RIGID DATA CONFLUENCE MET:</b>\n"
            f"• 🏁 <b>{session_name}</b> (Killzone Confirmed — 66.7% Win Rate)\n"
            f"• ⚡ <b>SMT Sponsorship ({smt_strength:.2f})</b> — 66.4% Win Rate\n"
            f"• ⏳ <b>Q2 Judas Window</b> (90-Min Manipulation)\n"
            f"• 💰 <b>Quartile Position ({price_quartile:.2f})</b> — 66.7% Win Rate\n\n"
            f"🛑 <b>Stop Loss:</b> ${stop_loss:,.2f}\n"
            f"🎯 <b>Full Target ({rr:.1f}R):</b> ${target:,.2f} (Est. +${target_pnl:,.2f} PnL)\n\n"
            f"⚠️ <b>PAYOUT DIRECTIVE:</b> This trade meets all 5 rigid statistical edge criteria. "
            f"Do NOT take early micro-exits. Allow trade to run to full {rr:.1f}R target."
        )
        self._send_message(msg, buttons=buttons)


# ── Standalone helpers ────────────────────────────────────────────────────────

def send_alert(symbol, timeframe, pattern, ai_score, reasoning, verdict="N/A",
               risk_calc=None, buttons=None, shadow_insights=None, security_status=None,
               regime_result=None, health_report=None, bias_data=None,
               liquidity_targets=None, session_info=None, psych_data=None,
               direction=None):
    TelegramNotifier().send_alert(
        symbol=symbol, timeframe=timeframe, pattern=pattern,
        ai_score=ai_score, reasoning=reasoning, verdict=verdict,
        risk_calc=risk_calc, buttons=buttons, shadow_insights=shadow_insights,
        security_status=security_status, regime_result=regime_result,
        health_report=health_report, bias_data=bias_data,
        liquidity_targets=liquidity_targets, session_info=session_info,
        psych_data=psych_data, direction=direction,
    )

def send_high_confluence_alert(symbol, direction, entry, stop_loss, target,
                               ai_score, smt_strength, session_name,
                               price_quartile, buttons=None):
    TelegramNotifier().send_high_confluence_alert(
        symbol=symbol, direction=direction, entry=entry,
        stop_loss=stop_loss, target=target, ai_score=ai_score,
        smt_strength=smt_strength, session_name=session_name,
        price_quartile=price_quartile, buttons=buttons
    )

def send_system_error(component, error):
    TelegramNotifier().send_system_error(component, error)

def send_message(text, buttons=None):
    TelegramNotifier()._send_message(text, buttons=buttons)
