import sqlite3
from datetime import datetime

conn = sqlite3.connect("data/smc_alpha.db")
cursor = conn.cursor()

cursor.execute("SELECT timestamp FROM journal")
rows = cursor.fetchall()

dates = []
for r in rows:
    ts = r[0]
    if ts:
        try:
            if str(ts).isdigit():
                if len(str(ts)) == 13:
                    dt = datetime.fromtimestamp(int(ts)/1000)
                else:
                    dt = datetime.fromtimestamp(int(ts))
            else:
                dt = datetime.fromisoformat(str(ts).replace("Z", ""))
            dates.append(dt)
        except Exception:
            pass

if dates:
    print(f"Earliest Trade: {min(dates)}")
    print(f"Latest Trade: {max(dates)}")
    print(f"Total Date Range: {(max(dates) - min(dates)).days} days")

conn.close()
