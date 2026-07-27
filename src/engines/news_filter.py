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

    def is_news_safe(self, buffer_pre_mins=1, buffer_post_mins=2):
        """
        Checks if we are in the exact T=0 spread-spike window of a Tier-1 event.
        - Returns False ONLY during [event_time - 1m, event_time + 2m] to protect against spread spikes.
        - Returns True for post-news Judas Reversal execution (T+2m to T+15m).
        """
        if not self.last_fetch or (datetime.now() - self.last_fetch).total_seconds() > 86400:
            self.fetch_calendar()

        now = datetime.now(pytz.timezone('US/Eastern'))
        
        for event in self.high_impact_events:
            try:
                event_time = datetime.fromisoformat(event['date'])
                diff_mins = (event_time - now).total_seconds() / 60.0
                
                # Block only during T-1m to T+2m to avoid T=0 spread spikes
                if -buffer_post_mins <= diff_mins <= buffer_pre_mins:
                    return False, event['title'], int(diff_mins)
            except Exception:
                continue
                
        return True, None, 0

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

if __name__ == "__main__":
    nf = NewsFilter()
    nf.fetch_calendar()
    safe, title, mins = nf.is_news_safe()
    print(f"Safe: {safe} | Event: {title} | Mins: {mins}")

