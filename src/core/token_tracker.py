import logging
from src.core.database import log_token_usage, get_daily_token_usage
from src.clients.telegram_notifier import TelegramNotifier

logger = logging.getLogger("TokenTracker")
notifier = TelegramNotifier()

# Default daily credit threshold in USD ($2.00 is very high for Flash, acting as a great safety ceiling)
DAILY_BUDGET_USD = 2.00
_warning_sent = False

def track_response_tokens(response, model_name="gemini-2.5-flash"):
    """
    Extracts usage_metadata from the response object, logs it to database,
    and checks if daily budget has been exceeded.
    """
    global _warning_sent
    if not response or not hasattr(response, "usage_metadata") or not response.usage_metadata:
        return
        
    try:
        prompt_tokens = response.usage_metadata.prompt_token_count or 0
        candidate_tokens = response.usage_metadata.candidates_token_count or 0
        
        # Log to local db
        log_token_usage(prompt_tokens, candidate_tokens, model_name=model_name)
        
        # Check budget limits
        stats = get_daily_token_usage()
        current_cost = stats.get("cost", 0.0)
        
        if current_cost >= DAILY_BUDGET_USD and not _warning_sent:
            msg = (
                f"⚠️ <b>TOKEN BUDGET CEILING EXCEEDED</b>\n"
                f"Your daily token cost has reached: <code>${current_cost:.4f}</code> / <code>${DAILY_BUDGET_USD:.2f}</code>\n"
                f"Please review the logs for unusual loop activity."
            )
            notifier._send_message(msg)
            _warning_sent = True
            logger.warning(f"Daily token budget ceiling exceeded: ${current_cost:.4f}")
            
    except Exception as e:
        logger.error(f"Failed to track tokens: {e}")
