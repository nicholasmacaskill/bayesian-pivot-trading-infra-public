import requests
import logging
from datetime import datetime, timedelta
import pytz

logger = logging.getLogger(__name__)

class NewsFilter:
    """
    Fetches High-Impact economic news (Red Folders) from ForexFactory.
    Acts as a 'Safety Switch' to pause the bot 30m before/after major events.
    """
    CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

    def __init__(self):
        self.high_impact_events = []
        self.last_fetch = None

    def fetch_calendar(self):
        """Fetches the weekly calendar and filters for High Impact USD news."""
        try:
            resp = requests.get(self.CALENDAR_URL, timeout=10)
            if resp.status_code == 200:
                events = resp.json()
                self.high_impact_events = [
                    e for e in events 
                    if e.get('impact') == 'High' and e.get('country') == 'USD'
                ]
                self.last_fetch = datetime.now()
                return True
        except Exception as e:
            logger.error(f"Error fetching news calendar: {e}")
        return False

    def is_news_safe(self, buffer_minutes=30):
        """
        Checks if we are within the black-out window of a High Impact event.
        Returns (is_safe: bool, event_name: str, minutes_until: int)
        """
        if not self.last_fetch or (datetime.now() - self.last_fetch).total_seconds() > 86400:  # 24 hours in seconds
            self.fetch_calendar()

        now = datetime.now(pytz.timezone('US/Eastern'))
        
        for event in self.high_impact_events:
            # ForexFactory dates are usually in ISO format with offset
            try:
                event_time = datetime.fromisoformat(event['date'])
                # Convert both to UTC for reliable comparison
                diff = (event_time - now).total_seconds() / 60
                
                if abs(diff) <= buffer_minutes:
                    return False, event['title'], int(diff)
            except Exception:
                continue
                
        return True, None, 0

if __name__ == "__main__":
    nf = NewsFilter()
    nf.fetch_calendar()
    safe, title, mins = nf.is_news_safe()
    print(f"Safe: {safe} | Event: {title} | Mins: {mins}")
