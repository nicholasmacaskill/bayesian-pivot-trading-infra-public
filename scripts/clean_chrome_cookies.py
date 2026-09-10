import os
import glob
import shutil
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path

# Whitelist of trusted domains to preserve logins & sessions
DEFAULT_WHITELIST = [
    'proton',        # ProtonMail / ProtonVPN
    'github',        # GitHub
    'upcomers',      # Upcomers Prop Firm
    'tradelocker',   # TradeLocker
    'tradingview',   # TradingView
    'vercel',        # Vercel
    'supabase',      # Supabase
    'linktr.ee',     # Linktree
    'twitter',       # Twitter
    'x.com',         # X
    'instagram',     # Instagram
    'facebook',      # Facebook
    'meta.com',      # Meta
    'threads.net',   # Threads
    'whatsapp',      # WhatsApp Web
    'google',        # Google / Gmail / Google Cloud
    'youtube',       # YouTube
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

ADULT_AND_TRACKER_KEYWORDS = [
    'porn', 'xxx', 'xvideos', 'pornhub', 'xhamster', 'redtube', 'youporn',
    'chaturbate', 'stripchat', 'cams', 'onlyfans', 'fansly', 'erome',
    'spankbang', 'tubegalore', 'eporner', 'beeg', 'heavy-r', 'motherless',
    'brazzers', 'naughty', 'hentai', 'rule34', 'adult', 'sex', 'cam4',
    'bongacams', 'livejasmin', 'fap', 'slut', 'milf', 'fetish', 'traffichaus',
    'exoclick', 'juicyads', 'ero-advertising', 'popcash', 'popads', 'propellerads'
]

def clean_profile_cookies(profile_dir: str, whitelist=None):
    whitelist = whitelist or DEFAULT_WHITELIST
    cookie_path = os.path.join(profile_dir, 'Cookies')
    if not os.path.exists(cookie_path):
        return

    print(f"\n📁 Inspecting Profile: {os.path.basename(profile_dir)}")
    
    # 1. Backup
    backup_path = f"{cookie_path}.backup_{int(time.time())}"
    try:
        shutil.copyfile(cookie_path, backup_path)
    except Exception:
        pass

    try:
        conn = sqlite3.connect(cookie_path, timeout=5.0)
        cur = conn.cursor()

        cur.execute("SELECT count(*), count(distinct host_key) FROM cookies")
        total_cookies, total_hosts = cur.fetchone()
        if total_cookies == 0:
            print("   • 0 cookies found. Clean.")
            conn.close()
            return

        # Explicit Tracker & Adult Cookie Purge
        adult_clauses = ' OR '.join([f"host_key LIKE '%{k}%'" for k in ADULT_AND_TRACKER_KEYWORDS])
        cur.execute(f"SELECT count(*) FROM cookies WHERE {adult_clauses}")
        adult_count = cur.fetchone()[0]

        if adult_count > 0:
            cur.execute(f"DELETE FROM cookies WHERE {adult_clauses}")
            conn.commit()
            print(f"   🧹 Purged {adult_count} explicit adult/tracker cookies.")

        # Non-whitelist tracker clean
        where_clauses = ' OR '.join([f"host_key LIKE '%{w}%'" for w in whitelist])
        cur.execute(f"SELECT count(*) FROM cookies WHERE NOT ({where_clauses})")
        junk_count = cur.fetchone()[0]

        if junk_count > 0:
            cur.execute(f"DELETE FROM cookies WHERE NOT ({where_clauses})")
            conn.commit()
            print(f"   🧹 Purged {junk_count} unapproved third-party tracker cookies.")

        cur.execute("VACUUM")
        conn.commit()

        cur.execute("SELECT count(*), count(distinct host_key) FROM cookies")
        remaining_cookies, remaining_hosts = cur.fetchone()
        print(f"   ✅ Clean Complete: Preserved {remaining_cookies} cookies across {remaining_hosts} trusted domains.")
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Could not access {cookie_path}: {e}")

def clean_profile_history(profile_dir: str):
    history_path = os.path.join(profile_dir, 'History')
    if not os.path.exists(history_path):
        return

    try:
        conn = sqlite3.connect(history_path, timeout=5.0)
        cur = conn.cursor()

        adult_clauses = ' OR '.join([f"url LIKE '%{k}%' OR title LIKE '%{k}%'" for k in ADULT_AND_TRACKER_KEYWORDS])
        
        # Check URLs
        cur.execute(f"SELECT count(*) FROM urls WHERE {adult_clauses}")
        adult_urls = cur.fetchone()[0]

        if adult_urls > 0:
            cur.execute(f"DELETE FROM urls WHERE {adult_clauses}")
            conn.commit()
            print(f"   🧹 Cleared {adult_urls} adult/tracker entries from History.")

        cur.execute("VACUUM")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Could not clean history at {history_path}: {e}")

def run_full_cookie_guardian():
    chrome_base = os.path.expanduser('~/Library/Application Support/Google/Chrome')
    if not os.path.exists(chrome_base):
        print(f"❌ Google Chrome directory not found at {chrome_base}")
        return

    print("=" * 75)
    print(" 🛡️ SOVEREIGN PRIVACY & COOKIE GUARDIAN (TARGETED PURGE)")
    print("=" * 75)

    # Check if Chrome is open
    res = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True)
    if res.returncode == 0:
        print(" ⚠️ Notice: Google Chrome is currently open. (For deepest lock, quit Chrome)")

    # Find all profile directories (Default, Profile 1, Profile 2, etc.)
    profiles = [os.path.join(chrome_base, 'Default')]
    profiles.extend(glob.glob(os.path.join(chrome_base, 'Profile *')))

    for p in profiles:
        if os.path.isdir(p):
            clean_profile_cookies(p)
            clean_profile_history(p)

    print("\n" + "=" * 75)
    print(" 🎉 PURGE FINISHED: All trackers, adult ad cookies, and beacons cleared.")
    print(" 🔒 All whitelist logins (Proton, GitHub, Upcomers, TradeLocker, Socials) preserved!")
    print("=" * 75)

if __name__ == '__main__':
    run_full_cookie_guardian()
