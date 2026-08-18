import os
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Default whitelist of critical domains to NEVER delete
DEFAULT_WHITELIST = [
    'proton',        # ProtonMail / ProtonVPN
    'github',        # GitHub
    'twitter',       # Twitter
    'x.com',         # X
    'instagram',     # Instagram (NEVER delete)
    'facebook',      # Facebook
    'meta.com',      # Meta
    'threads.net',   # Threads
    'whatsapp',      # WhatsApp Web
    'google',        # Google / Gmail / Google Cloud
    'youtube',       # YouTube
    'tradelocker',   # TradeLocker
    'tradingview',   # TradingView
    'reddit',        # Reddit
    'linkedin',      # LinkedIn
    'discord',       # Discord
    'telegram',      # Telegram Web
    'coinbase',      # Coinbase
    'binance',       # Binance
    'kraken',        # Kraken
    'bybit',         # Bybit
    'openai',        # ChatGPT / OpenAI
    'anthropic',     # Claude / Anthropic
    'openrouter',    # OpenRouter
    'gemini',        # Gemini
    'uber',          # Uber
    'amazon',        # Amazon
    'apple',         # Apple / iCloud
    'spotify',       # Spotify
    'substack',      # Substack
    'medium'         # Medium
]

def clean_chrome_cookies(whitelist=None, dry_run=False):
    whitelist = whitelist or DEFAULT_WHITELIST
    cookie_path = os.path.expanduser('~/Library/Application Support/Google/Chrome/Default/Cookies')

    if not os.path.exists(cookie_path):
        print(f"❌ Chrome cookies database not found at: {cookie_path}")
        return

    print("=" * 70)
    print(" 🧹 SMART CHROME COOKIE CLEANER (WHITELIST PRESERVATION)")
    print("=" * 70)

    # 1. Backup the Cookies database
    backup_path = f"{cookie_path}.backup_{int(time.time())}"
    shutil.copyfile(cookie_path, backup_path)
    print(f" • Created safety backup: {backup_path}")

    # 2. Check if Chrome is running
    res = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True)
    chrome_running = res.returncode == 0
    if chrome_running:
        print(" ⚠️  Google Chrome is currently open.")
        print("    (Chrome locks its database while open. For best results, quit Chrome with Cmd+Q)")

    # 3. Connect to SQLite database
    conn = sqlite3.connect(cookie_path)
    cur = conn.cursor()

    cur.execute("SELECT count(*), count(distinct host_key) FROM cookies")
    total_cookies, total_hosts = cur.fetchone()
    print(f" • Total Cookies before clean: {total_cookies} across {total_hosts} domains")

    # Construct Whitelist SQL Query
    where_clauses = ' OR '.join([f"host_key LIKE '%{w}%'" for w in whitelist])
    
    cur.execute(f"SELECT count(*) FROM cookies WHERE {where_clauses}")
    kept_count = cur.fetchone()[0]
    delete_count = total_cookies - kept_count

    print(f" • Preserved Critical Cookies: {kept_count}")
    print(f" • Junk / Tracker Cookies to Remove: {delete_count} ({(delete_count/total_cookies)*100:.1f}%)")

    if not dry_run:
        delete_sql = f"DELETE FROM cookies WHERE NOT ({where_clauses})"
        cur.execute(delete_sql)
        conn.commit()
        
        # Optimize and shrink database file
        cur.execute("VACUUM")
        conn.commit()
        print(f"\n ✅ Successfully deleted {delete_count} tracker cookies!")
        print(f" ✅ Database vacuumed & optimized. All critical logins (Proton, GitHub, Socials, Trading) preserved!")
    else:
        print("\n [DRY RUN] No changes written to database.")

    conn.close()
    print("=" * 70)

if __name__ == '__main__':
    clean_chrome_cookies(dry_run=False)
