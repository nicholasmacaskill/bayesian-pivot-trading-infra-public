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
        # Key format: f"{symbol}_{pattern}"
        self.last_alerts = {} 
        self.COOLDOWN_MINUTES = 60

    def send_alert(self, symbol, timeframe, pattern, ai_score, reasoning, verdict="N/A", risk_calc=None, buttons=None, shadow_insights=None, security_status=None):
        """Sends a formatted high-priority alert with optional execution buttons and shadow insights."""
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
        
        # Update timestamp for this alert
        self.last_alerts[alert_key] = current_time
            
        logger.info(f"Preparing Telegram alert for {symbol}...") # Force-refresh deployment

        # Format symbol for TradingView link (e.g., BTC/USDT -> BTCUSDT)
        tv_symbol = symbol.replace("/", "")
        tv_link = f"https://www.tradingview.com/chart/?symbol=BINANCE:{tv_symbol}"
        
        emoji = "🟢" if "Bullish" in pattern else "🔴"
        
        # Determine Signal Strength Title
        if ai_score >= 8.5:
             signal_type = "🦄 UNICORN SETUP"
        elif ai_score >= 7.5:
             signal_type = "🦅 HIGH ALPHA ALERT"
        else:
             signal_type = "⚠️ MED ALPHA ALERT"
        
        message = (
            f"{emoji} *{signal_type}*\n\n"
            f"🪙 *Symbol:* `{symbol}`\n"
            f"⚖️ *Verdict:* `{verdict}`\n"
            f"⏱️ *Timeframe:* `{timeframe}`\n"
            f"🔎 *Pattern:* {pattern}\n"
            f"🤖 *AI Score:* `{ai_score}/10`\n\n"
            f"🧠 *Analysis:* \n_{reasoning}_\n\n"
        )
        
        if risk_calc:
            position_size = risk_calc.get('position_size', 0.0)
            entry_price = risk_calc.get('entry', 0.0)
            position_value = position_size * entry_price
            
            # Robust TP extraction
            tp_price = risk_calc.get('take_profit') or risk_calc.get('target', 'OPEN')
            tp_str = f"${tp_price:,.2f}" if isinstance(tp_price, (int, float)) else str(tp_price)
            
            message += (
                f"🛡️ *Risk Management (0.75%):*\n"
                f"• Entry: `${entry_price:,.2f}`\n"
                f"• Stop: `${risk_calc.get('stop_loss', 0.0):,.2f}`\n"
                f"• TP: `{tp_str}`\n"
                f"• Position Size: `{position_size} {symbol.split('/')[0]}`\n"
                f"• Position Value: `${position_value:,.2f}`\n\n"
            )
        
        # Add Security Status (vibrant confirmation)
        if security_status:
            if "CLEAN" in security_status.upper() or "SECURE" in security_status.upper():
                status_formatted = "🛡️ *Security:* Environment confirmed as secure"
            else:
                status_formatted = f"⚠️ *Security:* {security_status}"
            message += f"{status_formatted}\n\n"

        # Add Shadow Optimizer Insights (if available)
        if shadow_insights:
            regime = shadow_insights.get('regime_classification', 'Unknown')
            multiplier = shadow_insights.get('suggested_risk_multiplier', 1.0)
            alpha_delta = shadow_insights.get('alpha_delta_prediction', 'N/A')
            slippage = shadow_insights.get('slippage_estimate', 'N/A')
            
            # Determine if shadow suggests deviation from control
            deviation_warning = ""
            if multiplier > 1.1:
                deviation_warning = "⚠️ Shadow suggests INCREASE (advisory only)"
            elif multiplier < 0.9:
                deviation_warning = "⚠️ Shadow suggests DECREASE (advisory only)"
            
            message += (
                f"🔬 *Shadow Optimizer (Experimental):*\n"
                f"• Regime: `{regime}`\n"
                f"• Suggested Risk: `{multiplier}x` ({multiplier * 0.75:.2f}%)\n"
                f"• Alpha Delta: {alpha_delta}\n"
                f"• Slippage Est: `{slippage}`\n"
            )
            
            if deviation_warning:
                message += f"{deviation_warning}\n"
            
            message += "\n"
            
        message += f"📊 [View on TradingView]({tv_link})"

        self._send_message(message, buttons=buttons)

    def send_security_alert(self, title: str, summary: str, severity: str = "HIGH"):
        """Sends a Sovereign Guard security threat alert to the Telegram channel."""
        severity_icon = {
            "CRITICAL": "🚨",
            "HIGH":     "⚠️",
            "MEDIUM":   "🟡",
        }.get(severity, "⚠️")

        message = (
            f"{severity_icon} *SOVEREIGN GUARD — {severity} ALERT*\n\n"
            f"🛡️ *{title}*\n\n"
            f"{summary}\n\n"
            f"⏰ `{__import__('datetime').datetime.now().strftime('%H:%M:%S UTC')}`"
        )
        self._send_message(message)

    def send_kill_switch(self, reason):
        """Sends a critical Kill Switch/Circuit Breaker alert."""
        message = (
            f"⚠️ *CIRCUIT BREAKER TRIGGERED* ⚠️\n\n"
            f"🛑 *System Halted*\n"
            f"Reason: {reason}\n\n"
            f"Trading suspended until manual reset or 00:00 UTC."
        )
        self._send_message(message)

    def send_system_error(self, component, error):
        """Sends a critical system error alert."""
        message = (
            f"🆘 *CRITICAL SYSTEM ERROR* 🆘\n\n"
            f"📍 *Component:* `{component}`\n"
            f"❌ *Error:* `{error[:300]}...`\n\n"
            f"Check dashboard or Modal logs for details."
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
            # We use a large limit to catch any bursts
            params = {"limit": 100, "allowed_updates": ["message"]}
            response = requests.get(url, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if not data.get("ok") or not data.get("result"):
                return None
                
            # Filter for messages from our chat_id and newer than since_timestamp
            valid_messages = []
            for update in data["result"]:
                msg = update.get("message")
                if not msg or str(msg.get("chat", {}).get("id")) != str(self.chat_id):
                    continue
                
                msg_text = msg.get("text")
                msg_ts = msg.get("date") # Unix timestamp
                
                if not msg_text:
                    continue
                    
                if since_timestamp and msg_ts <= since_timestamp:
                    continue
                    
                valid_messages.append({"text": msg_text, "timestamp": msg_ts})
                
            if valid_messages:
                # Return the absolute latest one
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
                    payload['parse_mode'] = "Markdown"
                response = requests.post(url, data=payload, files=files, timeout=10)
                response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Telegram photo: {e}")

# Standalone helper
def send_alert(symbol, timeframe, pattern, ai_score, reasoning, verdict="N/A", risk_calc=None, buttons=None, shadow_insights=None, security_status=None):
    notifier = TelegramNotifier()
    notifier.send_alert(symbol, timeframe, pattern, ai_score, reasoning, verdict, risk_calc, buttons=buttons, shadow_insights=shadow_insights, security_status=security_status)

def send_system_error(component, error):
    notifier = TelegramNotifier()
    notifier.send_system_error(component, error)
