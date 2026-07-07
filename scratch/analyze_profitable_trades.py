import sqlite3
import os
from collections import Counter
import re

db_path = "/Users/nicholasmacaskill/sovereignSMC/bayesian-pivot-trading-infra/data/smc_alpha.db"
if not os.path.exists(db_path):
    print(f"Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

try:
    c.execute("SELECT * FROM journal WHERE pnl > 0")
    rows = c.fetchall()
    
    strategies = []
    sides = []
    grades = []
    notes_texts = []
    deviations_texts = []
    symbols = []
    
    for row in rows:
        r = dict(row)
        strategies.append(r.get("strategy"))
        sides.append(r.get("side"))
        grades.append(r.get("ai_grade"))
        symbols.append(r.get("symbol"))
        if r.get("notes"):
            notes_texts.append(r.get("notes"))
        if r.get("deviations"):
            deviations_texts.append(r.get("deviations"))

    print(f"=== DEEP METRIC ANALYSIS OF PROFITABLE TRADES ===")
    print(f"Total Profitable Trades: {len(rows)}")
    
    print("\n1. Strategy Profile:")
    for k, v in Counter(strategies).items():
        print(f"  - {k}: {v} ({v/len(rows):.1%})")
        
    print("\n2. Directional Bias:")
    for k, v in Counter(sides).items():
        print(f"  - {k}: {v} ({v/len(rows):.1%})")
        
    print("\n3. AI Grade Distribution:")
    for k, v in sorted(Counter(grades).items(), key=lambda x: x[0], reverse=True):
        print(f"  - Grade {k}: {v} ({v/len(rows):.1%})")

    # Keyword analysis on notes/mentions
    keywords = ["trend", "bias", "volume", "reversal", "sweep", "grab", "support", "resistance", "liquidity", "early", "delay", "high", "low", "asian", "london", "ny", "session"]
    keyword_counts = Counter()
    
    combined_text = " ".join(notes_texts + deviations_texts).lower()
    for kw in keywords:
        # Match word boundaries
        matches = re.findall(rf"\b{kw}\b", combined_text)
        keyword_counts[kw] = len(matches)
        
    print("\n4. Core Structural Themes (Keyword Frequency in Notes & Deviations):")
    for kw, count in keyword_counts.most_common(12):
        print(f"  - '{kw}': {count} occurrences")
        
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
