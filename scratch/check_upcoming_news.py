import os
import sys
from datetime import datetime

# Add root to sys.path
sys.path.append(os.getcwd())

from src.engines.calendar_filter import CalendarFilter

def print_upcoming_events():
    cf = CalendarFilter()
    cf._fetch_events()
    now = datetime.utcnow()
    print(f"Current UTC Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 40)
    
    events = sorted(cf._events, key=lambda e: e['time_utc'])
    found = False
    for e in events:
        if e['time_utc'] > now:
            diff = e['time_utc'] - now
            hours = diff.total_seconds() / 3600
            if hours < 24:
                print(f"🔔 {e['time_utc'].strftime('%H:%M')} UTC | {e['currency']} | {e['title']} ({e['impact']})")
                found = True
    
    if not found:
        print("No high-impact news in the next 24 hours.")

if __name__ == "__main__":
    print_upcoming_events()
