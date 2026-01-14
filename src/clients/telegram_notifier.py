import logging
import requests
import os

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def send_alert(self, symbol, timeframe, pattern, ai_score, reasoning, verdict="N/A", risk_calc=None, buttons=None, shadow_insights=None):
        """Sends a formatted high-priority alert with optional execution buttons and shadow insights."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram credentials not found. Skipping alert.")
            return
            
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
            position_value = risk_calc['position_size'] * risk_calc['entry']
            message += (
                f"🛡️ *Risk Management (0.75%):*\n"
                f"• Entry: `${risk_calc['entry']:,.2f}`\n"
                f"• Stop: `${risk_calc['stop_loss']:,.2f}`\n"
                f"• TP: `${risk_calc.get('take_profit', 'OPEN')}`\n"
                f"• Position Size: `{risk_calc['position_size']} {symbol.split('/')[0]}`\n"
                f"• Position Value: `${position_value:,.2f}`\n\n"
            )
        
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

    def send_kill_switch(self, reason):
        """Sends a critical Kill Switch/Circuit Breaker alert."""
        message = (
            f"⚠️ *CIRCUIT BREAKER TRIGGERED* ⚠️\n\n"
            f"🛑 *System Halted*\n"
            f"Reason: {reason}\n\n"
            f"Trading suspended until manual reset or 00:00 UTC."
        )
        self._send_message(message)

    def _send_message(self, text, buttons=None):
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": True
            }
            if buttons:
                payload["reply_markup"] = {"inline_keyboard": buttons}
            response = requests.post(url, json=payload, timeout=5)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")

# Standalone helper
def send_alert(symbol, timeframe, pattern, ai_score, reasoning, verdict="N/A", risk_calc=None, buttons=None, shadow_insights=None):
    notifier = TelegramNotifier()
    notifier.send_alert(symbol, timeframe, pattern, ai_score, reasoning, verdict, risk_calc, buttons=buttons, shadow_insights=shadow_insights)
