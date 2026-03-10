import json
import logging
import requests
import os
from datetime import datetime

logger = logging.getLogger(__name__)


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
                   psych_data=None):
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
            tp    = risk_calc.get('take_profit', 'OPEN')
            tp_str = f"${tp:,.4f}" if isinstance(tp, (int, float)) else str(tp)
            exec_block = (
                f"\n💷 <b>EXECUTION</b>\n"
                f"• Entry: <code>${entry:,.4f}</code> | SL: <code>${sl:,.4f}</code> | TP: <code>{tp_str}</code>\n"
                f"• Lots: <code>{lots}</code>"
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
        emoji   = "🟢" if "Bullish" in pattern or "LONG" in pattern.upper() else "🔴"
        grade   = "🦄 UNICORN" if ai_score >= 8.5 else ("🦅 HIGH ALPHA" if ai_score >= 7.5 else "⚠️ MED ALPHA")

        # ── ASSEMBLE ──────────────────────────────────────────────────────────
        msg = (
            f"{emoji} <b>{grade}: {symbol}</b>\n"
            f"{header}\n\n"
            f"{confluence}\n\n"
            f"{liquidity}\n\n"
            f"{hunt}\n\n"
            f"{system_state}"
            f"{exec_block}\n\n"
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
                           latest_rejected: dict | None = None):
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
            f"🔍 <b>SOVEREIGN BRIEFING v3</b>\n"
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
            f"• DXY: <code>{dxy.get('trend','N/A')}</code> (<code>{dxy.get('change_5m',0):+.2f}%</code>)\n"
            f"• NQ: <code>{nq.get('trend','N/A')}</code> (<code>{nq.get('change_5m',0):+.2f}%</code>)\n"
            f"• TNX: <code>{tnx.get('trend','N/A')}</code> (<code>{tnx.get('change_5m',0):+.2f}%</code>)\n"
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
                f"💎 <b>Latest Call</b>: <code>{latest_setup.get('symbol','?')}</code> ({mins_ago}m ago)\n"
                f"  • Formation: <code>{latest_setup.get('pattern','N/A')}</code> | AI: <b>{latest_setup.get('ai_score','N/A')}/10</b>\n"
            )
        
        if latest_rejected:
            mins_ago_rej = latest_rejected.get('mins_ago', '?')
            if setup_block: setup_block += "\n"
            setup_block += (
                f"❌ <b>Latest Rejected</b>: <code>{latest_rejected.get('symbol','?')}</code> ({mins_ago_rej}m ago)\n"
                f"  • Formation: <code>{latest_rejected.get('pattern','N/A')}</code> | AI: <code>{latest_rejected.get('ai_score','N/A')}/10</code>\n"
            )

        if not setup_block:
            setup_block = "🔭 <b>Setups Today</b>\n  <i>No signals detected this session.</i>"

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
        msg = (
            f"{header}\n\n"
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
            f"{icon} <b>SOVEREIGN GUARD — {severity}</b>\n\n"
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


# ── Standalone helpers ────────────────────────────────────────────────────────

def send_alert(symbol, timeframe, pattern, ai_score, reasoning, verdict="N/A",
               risk_calc=None, buttons=None, shadow_insights=None, security_status=None,
               regime_result=None, health_report=None, bias_data=None,
               liquidity_targets=None, session_info=None, psych_data=None):
    TelegramNotifier().send_alert(
        symbol=symbol, timeframe=timeframe, pattern=pattern,
        ai_score=ai_score, reasoning=reasoning, verdict=verdict,
        risk_calc=risk_calc, buttons=buttons, shadow_insights=shadow_insights,
        security_status=security_status, regime_result=regime_result,
        health_report=health_report, bias_data=bias_data,
        liquidity_targets=liquidity_targets, session_info=session_info,
        psych_data=psych_data,
    )

def send_system_error(component, error):
    TelegramNotifier().send_system_error(component, error)
