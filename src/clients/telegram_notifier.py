import logging
import requests
import os

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        logger.info(f"📤 Notifier Initialized | Chat ID: {self.chat_id}")
        
        # Deduplication Tracker: {key: timestamp}
        self.last_alerts = {}
        self.COOLDOWN_MINUTES = 60

    def send_alert(self, symbol, timeframe, pattern, ai_score, reasoning,
                   verdict="N/A", risk_calc=None, buttons=None,
                   regime_result=None,       # RegimeResult object from regime_filter
                   health_report=None,       # dict from PropGuardian.check_account_health
                   bias_data=None,           # dict: {daily, htf, dxy_trend, smt_score}
                   liquidity_targets=None,   # dict: {target_price, target_type, distance_pips}
                   session_info=None,        # dict: {name, phase}
                   shadow_insights=None,
                   security_status=None):
        """
        Sends a 'Hierarchy of Edge' formatted alert with full institutional context.
        All new parameters are optional — degrades gracefully if not provided.
        """
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not found. Skipping alert.")
            return
            
        # DEDUPLICATION CHECK
        from datetime import datetime
        current_time = datetime.now()
        alert_key = f"{symbol}_{pattern}"
        
        if alert_key in self.last_alerts:
            last_time = self.last_alerts[alert_key]
            elapsed_minutes = (current_time - last_time).total_seconds() / 60
            if elapsed_minutes < self.COOLDOWN_MINUTES:
                logger.info(f"🤫 Smart Silence: Suppressing duplicate alert for {symbol} ({elapsed_minutes:.1f}m ago)")
                return
        
        self.last_alerts[alert_key] = current_time
        logger.info(f"Preparing Hierarchy of Edge alert for {symbol}...")

        # ── HEADER ────────────────────────────────────────────────────────────
        # Determine integrity badge from health_report DD vs 3% threshold
        dd_pct = 0.0
        if health_report:
            dd_pct = health_report.get('daily_drawdown', 0.0) * 100
        
        if dd_pct >= 3.0:
            integrity_badge = f"⚠️ <b>[INTEGRITY: WARNING]</b>"
        else:
            integrity_badge = f"🛡️ <b>[INTEGRITY: SECURE]</b>"
        
        dd_str = f"📉 <b>[DD: {dd_pct:.1f}% / 4.0%]</b>"
        
        sess_name  = session_info.get('name', 'UNKNOWN') if session_info else 'UNKNOWN'
        sess_phase = session_info.get('phase', '') if session_info else ''
        sess_str   = f"⏱️ <b>{sess_name}</b> ({sess_phase})" if sess_phase else f"⏱️ <b>{sess_name}</b>"
        
        header = f"{integrity_badge} | {dd_str} | {sess_str}"

        # ── CONFLUENCE ────────────────────────────────────────────────────────
        daily_bias = bias_data.get('daily', 'N/A') if bias_data else 'N/A'
        htf_bias   = bias_data.get('htf', 'N/A') if bias_data else 'N/A'
        dxy_trend  = bias_data.get('dxy_trend', 'N/A') if bias_data else 'N/A'
        smt_score  = bias_data.get('smt_score', 'N/A') if bias_data else 'N/A'
        
        confluence_block = (
            f"📐 <b>CONFLUENCE</b>\n"
            f"• Macro Bias: <code>{daily_bias}</code> | HTF Bias: <code>{htf_bias}</code>\n"
            f"• Pulse: DXY <code>{dxy_trend}</code> | SMT: <code>{smt_score}</code>"
        )

        # ── LIQUIDITY GRAVITY ─────────────────────────────────────────────────
        if liquidity_targets:
            next_draw   = liquidity_targets.get('target_price', 'N/A')
            draw_type   = liquidity_targets.get('target_type', 'N/A')
            dist_pips   = liquidity_targets.get('distance_pips', 'N/A')
            if isinstance(next_draw, float):
                next_draw = f"{next_draw:,.4f}"
            if isinstance(dist_pips, float):
                dist_pips = f"{dist_pips:.1f}"
            liq_block = (
                f"🎯 <b>LIQUIDITY GRAVITY</b>\n"
                f"• Next Draw: <code>{next_draw}</code> <i>({draw_type})</i>\n"
                f"• Buffer: <code>{dist_pips} pips</code>"
            )
        else:
            liq_block = f"🎯 <b>LIQUIDITY GRAVITY</b>\n• <i>No active HTF POI data.</i>"

        # ── THE HUNT ──────────────────────────────────────────────────────────
        hunt_block = (
            f"🦅 <b>THE HUNT</b>\n"
            f"• Stalking: <code>{pattern}</code> (<code>{ai_score}/10</code>)\n"
            f"• Logic: <i>{reasoning}</i>"
        )

        # ── RISK / SHADOW ─────────────────────────────────────────────────────
        size_mult    = f"{regime_result.suggested_size_mult:.2f}x" if regime_result and hasattr(regime_result, 'suggested_size_mult') else "1.00x"
        atr_pct_ile  = f"{regime_result.atr_percentile}th %ile" if regime_result and hasattr(regime_result, 'atr_percentile') else "N/A"
        slip_est     = shadow_insights.get('slippage_estimate', 'N/A') if shadow_insights else 'N/A'
        
        risk_shadow_block = (
            f"🔬 <b>RISK / SHADOW</b>\n"
            f"• Size: <code>{size_mult}</code> | Vol: <code>{atr_pct_ile}</code> | Slip: <code>{slip_est}</code>"
        )

        # ── RISK MANAGEMENT ───────────────────────────────────────────────────
        risk_block = ""
        if risk_calc:
            entry_price    = risk_calc.get('entry', 0.0)
            stop_loss      = risk_calc.get('stop_loss', 0.0)
            position_size  = risk_calc.get('position_size', 0.0)
            position_value = position_size * entry_price
            tp_price       = risk_calc.get('take_profit') or risk_calc.get('target', 'OPEN')
            tp_str         = f"${tp_price:,.4f}" if isinstance(tp_price, (int, float)) else str(tp_price)
            risk_block = (
                f"\n💷 <b>EXECUTION</b>\n"
                f"• Entry: <code>${entry_price:,.4f}</code> | Stop: <code>${stop_loss:,.4f}</code> | TP: <code>{tp_str}</code>\n"
                f"• Lots: <code>{position_size}</code> | Notional: <code>${position_value:,.2f}</code>"
            )

        # ── TRADINGVIEW LINK ──────────────────────────────────────────────────
        tv_symbol = symbol.replace("/", "")
        tv_link   = f"https://www.tradingview.com/chart/?symbol=BINANCE:{tv_symbol}"
        emoji     = "🟢" if "Bullish" in pattern else "🔴"

        if ai_score >= 8.5:
            signal_type = "🦄 UNICORN SETUP"
        elif ai_score >= 7.5:
            signal_type = "🦅 HIGH ALPHA ALERT"
        else:
            signal_type = "⚠️ MED ALPHA ALERT"

        # ── ASSEMBLE ──────────────────────────────────────────────────────────
        message = (
            f"{emoji} <b>{signal_type}: {symbol}</b>\n"
            f"{header}\n\n"
            f"{confluence_block}\n\n"
            f"{liq_block}\n\n"
            f"{hunt_block}\n\n"
            f"{risk_shadow_block}"
            f"{risk_block}\n\n"
            f"📊 <a href='{tv_link}'>View on TradingView</a>"
        )

        self._send_message(message, buttons=buttons)

    def send_security_alert(self, title: str, summary: str, severity: str = "HIGH"):
        """Sends a Sovereign Guard security threat alert to the Telegram channel."""
        severity_icon = {
            "CRITICAL": "🚨",
            "HIGH":     "⚠️",
            "MEDIUM":   "🟡",
        }.get(severity, "⚠️")

        message = (
            f"{severity_icon} <b>SOVEREIGN GUARD — {severity} ALERT</b>\n\n"
            f"🛡️ <b>{title}</b>\n\n"
            f"{summary}\n\n"
            f"⏰ <code>{__import__('datetime').datetime.now().strftime('%H:%M:%S UTC')}</code>"
        )
        self._send_message(message)

    def send_kill_switch(self, reason):
        """Sends a critical Kill Switch/Circuit Breaker alert."""
        message = (
            f"⚠️ <b>CIRCUIT BREAKER TRIGGERED</b> ⚠️\n\n"
            f"🛑 <b>System Halted</b>\n"
            f"Reason: {reason}\n\n"
            f"Trading suspended until manual reset or 00:00 UTC."
        )
        self._send_message(message)

    def send_system_error(self, component, error):
        """Sends a critical system error alert."""
        message = (
            f"🆘 <b>BAYESIAN PIVOT: CRITICAL ERROR</b> 🆘\n\n"
            f"📍 <b>Component:</b> <code>{component}</code>\n"
            f"❌ <b>Error:</b> <code>{str(error)[:300]}</code>\n\n"
            f"Check local logs for details."
        )
        self._send_message(message)

    def _send_message(self, text, buttons=None):
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            
            response = requests.post(url, json=payload, timeout=5)
            logger.info(f"📤 Telegram Response ({response.status_code}): {response.text[:100]}")
            response.raise_for_status()
        except Exception as e:
            logger.error(f"❌ Failed to send Telegram message: {e}")
            if 'response' in locals():
                logger.error(f"❌ Error Detail: {response.text}")

    def get_latest_message(self, since_timestamp=None):
        """Fetches the latest text message from the chat."""
        try:
            url = f"{self.base_url}/getUpdates"
            params = {"limit": 100, "allowed_updates": ["message"]}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("ok") or not data.get("result"):
                return None
                
            valid_messages = []
            for update in data["result"]:
                msg = update.get("message")
                if not msg or str(msg.get("chat", {}).get("id")) != str(self.chat_id):
                    continue
                
                msg_text = msg.get("text")
                msg_ts   = msg.get("date")
                
                if not msg_text:
                    continue
                if since_timestamp and msg_ts <= since_timestamp:
                    continue
                    
                valid_messages.append({"text": msg_text, "timestamp": msg_ts})
                
            if valid_messages:
                return sorted(valid_messages, key=lambda x: x['timestamp'])[-1]
                
            return None
        except Exception as e:
            logger.error(f"Failed to fetch Telegram updates: {e}")
            return None

    def send_photo(self, photo_path, caption=None):
        """Sends a photo with an optional caption."""
        if not self.bot_token or not self.chat_id:
            return
        try:
            url = f"{self.base_url}/sendPhoto"
            with open(photo_path, 'rb') as photo:
                files = {'photo': photo}
                payload = {'chat_id': self.chat_id}
                if caption:
                    payload['caption'] = caption
                    payload['parse_mode'] = "HTML"
                response = requests.post(url, data=payload, files=files, timeout=10)
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Telegram photo: {e}")


# Standalone helpers
def send_alert(symbol, timeframe, pattern, ai_score, reasoning, verdict="N/A",
               risk_calc=None, buttons=None, shadow_insights=None, security_status=None,
               regime_result=None, health_report=None, bias_data=None,
               liquidity_targets=None, session_info=None):
    notifier = TelegramNotifier()
    notifier.send_alert(
        symbol=symbol, timeframe=timeframe, pattern=pattern,
        ai_score=ai_score, reasoning=reasoning, verdict=verdict,
        risk_calc=risk_calc, buttons=buttons, shadow_insights=shadow_insights,
        security_status=security_status, regime_result=regime_result,
        health_report=health_report, bias_data=bias_data,
        liquidity_targets=liquidity_targets, session_info=session_info,
    )

def send_system_error(component, error):
    notifier = TelegramNotifier()
    notifier.send_system_error(component, error)
