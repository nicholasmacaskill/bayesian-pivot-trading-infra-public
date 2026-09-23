import requests
import logging
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

# Tier-1 US Macro Events that impact BTC and ETH
CRYPTO_CATALYST_WHITELIST = [
    'FOMC', 'FEDERAL FUNDS', 'CPI', 'CONSUMER PRICE INDEX', 
    'NON-FARM', 'NFP', 'UNEMPLOYMENT RATE', 'PCE', 'PPI', 'FED CHAIR'
]

class NewsFilter:
    """
    Fetches Tier-1 High-Impact US economic news (Red Folders) from ForexFactory.
    Filters specifically for USD macro events that impact BTC and ETH.
    Pauses execution at T=0 seconds to avoid spread spikes, but unblocks T+2m to T+15m
    for Post-News Judas Reversal setups.
    """
    CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    def __init__(self):
        self.high_impact_events = []
        self.last_fetch = None

    def is_crypto_catalyst(self, event_title: str) -> bool:
        """Checks if event title matches Tier-1 USD crypto macro whitelist."""
        title_upper = str(event_title).upper()
        return any(kw in title_upper for kw in CRYPTO_CATALYST_WHITELIST)

    def fetch_calendar(self, currencies=['USD']):
        """Fetches weekly calendar and filters for Tier-1 High Impact USD news relevant to Crypto."""
        try:
            resp = requests.get(self.CALENDAR_URL, timeout=10)
            if resp.status_code == 200:
                events = resp.json()
                self.high_impact_events = [
                    e for e in events 
                    if e.get('impact') == 'High' 
                    and e.get('country') in currencies
                    and self.is_crypto_catalyst(e.get('title', ''))
                ]
                self.last_fetch = datetime.now()
                logger.info(f"📰 NewsFilter: Loaded {len(self.high_impact_events)} Tier-1 Crypto Macro USD events")
                return True
        except Exception as e:
            logger.error(f"Error fetching news calendar: {e}")
        return False

    def is_news_safe(self, symbol=None, buffer_pre_mins=None, buffer_post_mins=None, buffer_minutes=None):
        """
        Checks if we are in the high-impact news blackout window.
        - Crypto (BTC/ETH/SOL): Pre-news 1m, Post-news 2m (allows Post-News Judas Reversals T+2m to T+15m).
        - Commodities / Gold (XAU/USD): Pre-news 5m, Post-news 5m to shield against spread blowouts & extreme volatility.
        - Custom buffer_minutes or buffer_pre_mins/buffer_post_mins can override.
        """
        if not self.last_fetch or (datetime.now() - self.last_fetch).total_seconds() > 86400:
            self.fetch_calendar()

        is_gold = symbol and any(g in str(symbol).upper() for g in ["XAU", "GOLD"])

        if buffer_minutes is not None:
            pre_mins = buffer_minutes
            post_mins = buffer_minutes
        else:
            if is_gold:
                pre_mins = 5 if buffer_pre_mins is None else buffer_pre_mins
                post_mins = 5 if buffer_post_mins is None else buffer_post_mins
            else:
                pre_mins = 1 if buffer_pre_mins is None else buffer_pre_mins
                post_mins = 2 if buffer_post_mins is None else buffer_post_mins

        now = datetime.now(pytz.timezone('US/Eastern'))
        
        for event in self.high_impact_events:
            try:
                event_time = datetime.fromisoformat(event['date'])
                diff_mins = (event_time - now).total_seconds() / 60.0
                
                # Block during [-post_mins, pre_mins]
                if -post_mins <= diff_mins <= pre_mins:
                    return False, event['title'], int(diff_mins)
            except Exception:
                continue
                
        return True, None, 0

    def is_trade_allowed(self, symbol="BTC/USD"):
        """Convenience method returning (is_allowed, event_title, diff_mins) for a specific symbol."""
        return self.is_news_safe(symbol=symbol)

    def get_upcoming_catalyst(self, window_mins=15):
        """Returns details if a Tier-1 Crypto Macro catalyst is within `window_mins`."""
        if not self.last_fetch:
            self.fetch_calendar()

        now = datetime.now(pytz.timezone('US/Eastern'))
        for event in self.high_impact_events:
            try:
                event_time = datetime.fromisoformat(event['date'])
                diff_mins = (event_time - now).total_seconds() / 60.0
                if 0 <= diff_mins <= window_mins:
                    return True, event['title'], int(diff_mins), event_time
            except Exception:
                continue
        return False, None, 0, None

    def is_safe_to_trade(self, symbol=None):
        safe, event, mins = self.is_news_safe(symbol=symbol)
        reason = f"News Event: {event} in {mins}m" if not safe else "OK"
        return safe, reason

if __name__ == "__main__":
    nf = NewsFilter()
    nf.fetch_calendar()
    safe, title, mins = nf.is_news_safe()
    print(f"Safe: {safe} | Event: {title} | Mins: {mins}")

