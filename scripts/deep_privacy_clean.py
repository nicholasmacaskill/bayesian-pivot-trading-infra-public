import os
import glob
import shutil
import sqlite3
import subprocess
import time

ADULT_AND_TRACKER_KEYWORDS = [
    'porn', 'xxx', 'xvideos', 'pornhub', 'xhamster', 'redtube', 'youporn',
    'chaturbate', 'stripchat', 'cams', 'onlyfans', 'fansly', 'erome',
    'spankbang', 'tubegalore', 'eporner', 'beeg', 'heavy-r', 'motherless',
    'brazzers', 'naughty', 'hentai', 'rule34', 'adult', 'sex', 'cam4',
    'bongacams', 'livejasmin', 'fap', 'slut', 'milf', 'fetish', 'traffichaus',
    'exoclick', 'juicyads', 'ero-advertising', 'popcash', 'popads', 'propellerads',
    'camsoda', 'imlive', 'myfreecams', 'camwhores', 'fuq', 'nuvid', 'drtuber',
    'xmovies', 'tnaflix', 'porntrex', 'daftsex', 'sunporno', 'gotporn'
]

DEFAULT_WHITELIST = [
    'proton', 'github', 'upcomers', 'tradelocker', 'tradingview', 'vercel',
    'supabase', 'linktr.ee', 'twitter', 'x.com', 'instagram', 'facebook',
    'meta.com', 'threads.net', 'whatsapp', 'google', 'youtube', 'reddit',
    'linkedin', 'discord', 'telegram', 'coinbase', 'binance', 'kraken',
    'bybit', 'openai', 'anthropic', 'openrouter', 'gemini', 'uber',
    'amazon', 'apple', 'spotify', 'substack', 'medium'
]

def kill_chrome():
    """Closes Chrome so SQLite files are unlocked."""
    print("🛑 Gracefully closing Google Chrome to unlock autocomplete databases...")
    try:
        subprocess.run(["osascript", "-e", 'tell application "Google Chrome" to quit'], timeout=5)
        time.sleep(1.5)
    except Exception:
        pass
    subprocess.run(["pkill", "-9", "-f", "Google Chrome"])
    time.sleep(1.0)

def clean_history_db(db_path: str):
    if not os.path.exists(db_path): return
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cur = conn.cursor()
        clauses = ' OR '.join([f"url LIKE '%{k}%' OR title LIKE '%{k}%'" for k in ADULT_AND_TRACKER_KEYWORDS])
        
        # 1. Clean urls table
        cur.execute(f"SELECT count(*) FROM urls WHERE {clauses}")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            cur.execute(f"DELETE FROM urls WHERE {clauses}")
            print(f"   🧹 Purged {cnt} URLs from History ({os.path.basename(os.path.dirname(db_path))})")

        # 2. Clean visits table matching deleted urls
        try:
            cur.execute("DELETE FROM visits WHERE url NOT IN (SELECT id FROM urls)")
        except Exception:
            pass

        # 3. Clean keyword_search_terms
        try:
            kw_clauses = ' OR '.join([f"term LIKE '%{k}%' OR normalized_term LIKE '%{k}%'" for k in ADULT_AND_TRACKER_KEYWORDS])
            cur.execute(f"DELETE FROM keyword_search_terms WHERE {kw_clauses}")
        except Exception:
            pass

        conn.commit()
        cur.execute("VACUUM")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ History clean error ({db_path}): {e}")

def clean_shortcuts_db(db_path: str):
    """Purges Omnibox / URL address bar autocomplete suggestions."""
    if not os.path.exists(db_path): return
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cur = conn.cursor()
        clauses = ' OR '.join([f"url LIKE '%{k}%' OR text LIKE '%{k}%' OR fill_into_edit LIKE '%{k}%'" for k in ADULT_AND_TRACKER_KEYWORDS])
        
        cur.execute(f"SELECT count(*) FROM omni_box_shortcuts WHERE {clauses}")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            cur.execute(f"DELETE FROM omni_box_shortcuts WHERE {clauses}")
            print(f"   🧹 Purged {cnt} Omnibox Autocomplete Shortcuts ({os.path.basename(os.path.dirname(db_path))})")
        else:
            print(f"   ✨ Omnibox Shortcuts clean ({os.path.basename(os.path.dirname(db_path))})")

        conn.commit()
        cur.execute("VACUUM")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Shortcuts clean error: {e}")

def clean_predictor_db(db_path: str):
    """Purges Network Action Predictor (Search & URL predictive completions)."""
    if not os.path.exists(db_path): return
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cur = conn.cursor()
        clauses = ' OR '.join([f"user_text LIKE '%{k}%' OR url LIKE '%{k}%'" for k in ADULT_AND_TRACKER_KEYWORDS])
        
        cur.execute(f"SELECT count(*) FROM network_action_predictor WHERE {clauses}")
        cnt = cur.fetchone()[0]
        if cnt > 0:
            cur.execute(f"DELETE FROM network_action_predictor WHERE {clauses}")
            print(f"   🧹 Purged {cnt} URL Predictor Entries ({os.path.basename(os.path.dirname(db_path))})")

        conn.commit()
        cur.execute("VACUUM")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"   ⚠️ Predictor clean error: {e}")

def clean_top_sites_db(db_path: str):
    """Purges New Tab 'Top Sites' suggestions."""
    if not os.path.exists(db_path): return
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cur = conn.cursor()
        clauses = ' OR '.join([f"url LIKE '%{k}%' OR title LIKE '%{k}%'" for k in ADULT_AND_TRACKER_KEYWORDS])
        
        cur.execute(f"DELETE FROM top_sites WHERE {clauses}")
        conn.commit()
        cur.execute("VACUUM")
        conn.commit()
        conn.close()
    except Exception as e:
        pass

def clean_cookies_db(db_path: str):
    if not os.path.exists(db_path): return
    try:
        conn = sqlite3.connect(db_path, timeout=5.0)
        cur = conn.cursor()
        adult_clauses = ' OR '.join([f"host_key LIKE '%{k}%'" for k in ADULT_AND_TRACKER_KEYWORDS])
        cur.execute(f"DELETE FROM cookies WHERE {adult_clauses}")
        
        where_clauses = ' OR '.join([f"host_key LIKE '%{w}%'" for w in DEFAULT_WHITELIST])
        cur.execute(f"DELETE FROM cookies WHERE NOT ({where_clauses})")
        conn.commit()
        cur.execute("VACUUM")
        conn.commit()
        conn.close()
    except Exception as e:
        pass

def relaunch_chrome():
    print("🚀 Relaunching clean Google Chrome...")
    subprocess.Popen(["open", "-a", "Google Chrome"])

def main():
    print("=" * 75)
    print(" 🧹 COMPLETE OMNIBOX, AUTOCOMPLETE & HISTORY DEEP PURGE")
    print("=" * 75)

    kill_chrome()

    chrome_base = os.path.expanduser('~/Library/Application Support/Google/Chrome')
    profiles = [os.path.join(chrome_base, 'Default')]
    profiles.extend(glob.glob(os.path.join(chrome_base, 'Profile *')))

    for p in profiles:
        if os.path.isdir(p):
            print(f"\n📁 Cleaning Profile: {os.path.basename(p)}")
            clean_history_db(os.path.join(p, 'History'))
            clean_shortcuts_db(os.path.join(p, 'Shortcuts'))
            clean_predictor_db(os.path.join(p, 'Network Action Predictor'))
            clean_top_sites_db(os.path.join(p, 'Top Sites'))
            clean_cookies_db(os.path.join(p, 'Cookies'))

    print("\n" + "=" * 75)
    print(" ✅ DEEP PURGE COMPLETE: Omnibox suggestions, History & Predictors cleared.")
    print("=" * 75)
    
    relaunch_chrome()

if __name__ == '__main__':
    main()
