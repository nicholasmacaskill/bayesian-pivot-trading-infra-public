import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engines.calendar_filter import CalendarFilter

def check_news():
    cf = CalendarFilter()
    
    # Force fetch
    cf._fetch_events()
    
    print("Checking systemic macro event blocks (Red Folder News)...\n")
    events = cf._events
    if not events:
        print("No high-impact events scheduled.")
    else:
        print("High Impact Events Detected:")
        for ev in events:
            print(f"- {ev['time_utc']} UTC: {ev['title']} ({ev['currency']}) - Impact: {ev['impact']}")
    
    next_ev = cf.next_event_info()
    if next_ev:
        print(f"\nNEXT UPCOMING EVENT: {next_ev['title']} in {next_ev['minutes_until']} minutes.")
    else:
        print("\nNo events in the next 24 hours.")

if __name__ == "__main__":
    check_news()
