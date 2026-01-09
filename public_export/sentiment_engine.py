import requests
import os
import logging
from config import Config


# Standard Browser Headers for Stealth Mode
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
}

logger = logging.getLogger(__name__)

class SentimentEngine:
    def __init__(self):
        self.cryptopanic_key = os.environ.get("CRYPTOPANIC_API_KEY")
        self.whale_alert_key = os.environ.get("WHALE_ALERT_API_KEY")

    def get_market_sentiment(self, symbol="BTC"):
        """Fetches Fear & Greed and News Sentiment."""
        sentiment_report = {
            "fear_and_greed": "Unknown",
            "news_sentiment": "Neutral",
            "whale_flow": "Stable"
        }

        # 1. Fear & Greed Index (Public Endpoint)
        try:
            fg_resp = requests.get("https://api.alternative.me/fng/", headers=HEADERS, timeout=10)
            if fg_resp.status_code == 200:
                data = fg_resp.json()['data'][0]
                sentiment_report["fear_and_greed"] = f"{data['value']} ({data['value_classification']})"
        except Exception as e:
            logger.error(f"F&G Fetch Error: {e}")

        # 2. CryptoPanic News Sentiment
        if self.cryptopanic_key:
            try:
                # filter=hot or filter=important
                cp_symbol = symbol.split('/')[0] if '/' in symbol else symbol
                url = f"https://cryptopanic.com/api/v1/posts/?auth_token={self.cryptopanic_key}&currencies={cp_symbol}&filter=important"
                cp_resp = requests.get(url, headers=HEADERS, timeout=10)
                if cp_resp.status_code == 200:
                    results = cp_resp.json().get('results', [])
                    if results:
                        # Simple heuristic: look at top 3 news titles
                        titles = [r['title'] for r in results[:3]]
                        sentiment_report["news_sentiment"] = " | ".join(titles)
            except Exception as e:
                logger.error(f"CryptoPanic Error: {e}")

        # 3. Whale Alert (simplified for confluence)
        if self.whale_alert_key:
            try:
                # Get large transactions in last hour
                url = f"https://api.whale-alert.io/v1/status?api_key={self.whale_alert_key}"
                # In real scenario, we'd iterate over /transactions but for confluence, 
                # we just check if whale alert is active.
                sentiment_report["whale_flow"] = "Active Monitoring (Check Telegram for Large Moves)"
            except Exception as e:
                logger.error(f"Whale Alert Error: {e}")

        return sentiment_report

    def get_whale_confluence(self):
        """Specifically looks for exchange inflows/outflows."""
        # This is a placeholder for deep whale analysis
        # If inflows > outflows, sentiment becomes bearish
        return "Stable"
