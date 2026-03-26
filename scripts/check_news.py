import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engines.calendar_filter import CalendarFilter

def check_news():
    cf = CalendarFilter()
    print("Checking systemic macro event blocks (Red Folder News)...\n")
    events = cf._get_cached_calendar()
    if not events:
        print("No high-impact events scheduled today.")
    else:
        print("High Impact Events Detected:")
        for ev in events:
            print(f"- {ev['time']}: {ev['title']} (Impact: {ev['impact']})")
    
    # Also check if we are currently globally blocked
    blocked = not cf.is_trade_allowed("BTC/USD")
    print(f"\nAlgorithmic Trading Blocked by News Phase? {blocked}")

if __name__ == "__main__":
    check_news()
