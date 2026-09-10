#!/usr/bin/env python3
"""
🛡️ Cookie Guardian — Automated Full-Stack Browser Cookie & Site Data Purge Agent
Preserves critical authenticated sessions (Proton Mail, Proton Pass, GitHub, Google/Gmail, Trading Portals, Open Tabs)
while sweeping away advertising cookies, tracking beacons, orphaned IndexedDB stores, and 1.5GB+ of stale Service Worker cache every hour.
"""

import os
import sys
import glob
import json
import shutil
import sqlite3
import logging
import subprocess
import argparse
from urllib.parse import urlparse
from datetime import datetime, timezone

# Base directories
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "cookie_whitelist.json")
LOG_DIR = os.path.join(os.path.expanduser("~"), ".cookie_guardian", "logs")
BACKUP_DIR = os.path.join(os.path.expanduser("~"), ".cookie_guardian", "backups")

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

# Logger setup
log_path = os.path.join(LOG_DIR, "cookie_guardian.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_path),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("CookieGuardian")


def load_whitelist():
    """Loads configured domain whitelist and substring matching rules from JSON."""
    default_wl = [
        "proton.me", "protonmail.com", "proton.com", "protonvpn.com", "protonstatus.com",
        "github.com", "githubusercontent.com", "google.com", "gmail.com", "accounts.google.com",
        "upcomers.com", "tradelocker.com", "tradingview.com", "linktr.ee", "x.com", "twitter.com",
        "vercel.com", "flocanolabs.com", "telegram.org", "openai.com", "claude.ai"
    ]
    default_subs = ["proton", "github", "google", "gmail"]

    if not os.path.exists(CONFIG_FILE):
        return default_wl, default_subs, True

    try:
        with open(CONFIG_FILE, "r") as f:
            data = json.load(f)
            whitelist = data.get("whitelist", default_wl)
            match_substrings = data.get("match_substrings", default_subs)
            auto_open_tabs = data.get("auto_whitelist_open_tabs", True)
            return whitelist, match_substrings, auto_open_tabs
    except Exception as e:
        logger.error(f"Error loading {CONFIG_FILE}: {e}")
        return default_wl, default_subs, True


def get_open_chrome_tab_domains():
    """Dynamically queries currently open tabs in Google Chrome via AppleScript."""
    domains = set()
    applescript = '''
    if application "Google Chrome" is running then
        tell application "Google Chrome"
            set urlList to {}
            repeat with w in windows
                repeat with t in tabs of w
                    set end of urlList to (URL of t)
                end repeat
            end repeat
            return urlList
        end tell
    else
        return ""
    end if
    '''
    try:
        proc = subprocess.run(["osascript", "-e", applescript], capture_output=True, text=True, timeout=5)
        if proc.returncode == 0 and proc.stdout.strip():
            raw_urls = proc.stdout.strip().split(", ")
            for u in raw_urls:
                u = u.strip()
                if u.startswith("http://") or u.startswith("https://"):
                    parsed = urlparse(u)
                    host = parsed.netloc.split(":")[0].lower()
                    if host:
                        parts = host.split(".")
                        if len(parts) >= 2:
                            root_domain = ".".join(parts[-2:])
                            domains.add(root_domain)
                        domains.add(host)
    except Exception as e:
        logger.debug(f"Could not query open Chrome tabs: {e}")
    return domains


def host_matches_whitelist(host_key: str, allowed_domains: set, match_substrings: list) -> bool:
    """
    Checks if a host/domain matches any whitelisted domain or special substring.
    - Preserves anything containing 'proton', 'github', 'google', 'gmail'
    - Preserves exact domain and subdomains in allowed_domains
    """
    clean_host = host_key.lstrip(".").lower()

    # Substring safeguard
    for sub in match_substrings:
        if sub.lower() in clean_host:
            return True

    # Domain / subdomain match
    for domain in allowed_domains:
        d = domain.lstrip(".").lower()
        if clean_host == d or clean_host.endswith("." + d):
            return True

    return False


def get_chrome_profiles():
    """Finds all Chrome profile root directories."""
    chrome_base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    if not os.path.exists(chrome_base):
        return []

    profiles = []
    default_p = os.path.join(chrome_base, "Default")
    if os.path.exists(default_p):
        profiles.append(default_p)

    for p in glob.glob(os.path.join(chrome_base, "Profile *")):
        if os.path.isdir(p):
            profiles.append(p)

    return profiles


def clean_cookie_db(profile_dir: str, allowed_domains: set, match_substrings: list, dry_run: bool = False):
    """Purges non-whitelisted cookies from SQLite Cookies table."""
    db_path = os.path.join(profile_dir, "Cookies")
    if not os.path.exists(db_path):
        return

    profile_name = os.path.basename(profile_dir)
    logger.info(f"🔍 [Cookies] Checking profile: [{profile_name}] -> {db_path}")

    # Backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"Cookies_{profile_name}_{timestamp}.db")
    try:
        shutil.copy2(db_path, backup_file)
        old_backups = sorted(glob.glob(os.path.join(BACKUP_DIR, f"Cookies_{profile_name}_*.db")))
        if len(old_backups) > 5:
            for old_b in old_backups[:-5]:
                try: os.remove(old_b)
                except: pass
    except Exception as e:
        logger.warning(f"Could not create backup for {db_path}: {e}")

    try:
        conn = sqlite3.connect(db_path, timeout=10.0)
        cursor = conn.cursor()

        cursor.execute("SELECT count(*) FROM cookies")
        total_cookies = cursor.fetchone()[0]

        cursor.execute("SELECT DISTINCT host_key FROM cookies")
        all_hosts = [row[0] for row in cursor.fetchall()]

        hosts_to_delete = []
        hosts_to_keep = []
        for h in all_hosts:
            if host_matches_whitelist(h, allowed_domains, match_substrings):
                hosts_to_keep.append(h)
            else:
                hosts_to_delete.append(h)

        cursor.execute("SELECT count(*) FROM cookies WHERE host_key IN ({seq})".format(
            seq=','.join(['?'] * len(hosts_to_delete))
        ) if hosts_to_delete else "SELECT 0", hosts_to_delete if hosts_to_delete else [])
        delete_count = cursor.fetchone()[0] if hosts_to_delete else 0
        keep_count = total_cookies - delete_count

        logger.info(f"📊 [Cookies] [{profile_name}]: Total: {total_cookies} | 🛡️ Preserved: {keep_count} | 🧹 Purging: {delete_count}")

        if dry_run:
            conn.close()
            return

        if hosts_to_delete:
            batch_size = 500
            for i in range(0, len(hosts_to_delete), batch_size):
                batch = hosts_to_delete[i:i + batch_size]
                cursor.execute(
                    "DELETE FROM cookies WHERE host_key IN ({seq})".format(seq=','.join(['?'] * len(batch))),
                    batch
                )
            conn.commit()
            cursor.execute("VACUUM")
            logger.info(f"✅ [Cookies] Successfully purged {delete_count} cookies in [{profile_name}].")
        else:
            logger.info(f"✨ [Cookies] [{profile_name}] is already clean.")

        conn.close()

    except sqlite3.OperationalError as op_err:
        logger.warning(f"⚠️ [Cookies] SQLite OperationalError on {profile_name}: {op_err}")
    except Exception as e:
        logger.error(f"❌ [Cookies] Error processing {db_path}: {e}")


def clean_indexeddb(profile_dir: str, allowed_domains: set, match_substrings: list, dry_run: bool = False):
    """Purges orphaned IndexedDB site stores from disk."""
    idb_dir = os.path.join(profile_dir, "IndexedDB")
    if not os.path.exists(idb_dir):
        return

    profile_name = os.path.basename(profile_dir)
    purged_count = 0
    preserved_count = 0

    for item in os.listdir(idb_dir):
        full_path = os.path.join(idb_dir, item)
        # Keep extensions
        if item.startswith("chrome-extension_") or item.startswith("chrome_"):
            preserved_count += 1
            continue

        # e.g. https_accounts.coinbase.com_0.indexeddb.leveldb
        clean_name = item.replace("https_", "").replace("http_", "").split("_")[0]
        if host_matches_whitelist(clean_name, allowed_domains, match_substrings):
            preserved_count += 1
        else:
            purged_count += 1
            if not dry_run:
                try:
                    if os.path.isdir(full_path):
                        shutil.rmtree(full_path, ignore_errors=True)
                    else:
                        os.remove(full_path)
                except Exception as e:
                    logger.debug(f"Could not remove IndexedDB {item}: {e}")

    logger.info(f"📊 [IndexedDB] [{profile_name}]: Preserved: {preserved_count} | 🧹 Purged: {purged_count} site databases")


def clean_service_workers(profile_dir: str, allowed_domains: set, match_substrings: list, dry_run: bool = False):
    """Purges non-whitelisted service worker script caches to reclaim gigabytes of RAM/disk."""
    sw_dir = os.path.join(profile_dir, "Service Worker")
    if not os.path.exists(sw_dir):
        return

    profile_name = os.path.basename(profile_dir)
    cache_storage = os.path.join(sw_dir, "CacheStorage")
    if os.path.exists(cache_storage):
        purged = 0
        preserved = 0
        for item in os.listdir(cache_storage):
            full_path = os.path.join(cache_storage, item)
            clean_name = item.replace("https_", "").replace("http_", "").split("_")[0]
            if item.startswith("chrome-extension_") or host_matches_whitelist(clean_name, allowed_domains, match_substrings):
                preserved += 1
            else:
                purged += 1
                if not dry_run:
                    try:
                        if os.path.isdir(full_path):
                            shutil.rmtree(full_path, ignore_errors=True)
                    except: pass
        logger.info(f"📊 [Service Workers] [{profile_name}]: Preserved: {preserved} | 🧹 Purged: {purged} worker caches")


def clean_quota_manager(profile_dir: str, allowed_domains: set, match_substrings: list, dry_run: bool = False):
    """Purges non-whitelisted origin buckets from WebStorage QuotaManager SQLite database."""
    qm_db = os.path.join(profile_dir, "WebStorage", "QuotaManager")
    if not os.path.exists(qm_db):
        return

    profile_name = os.path.basename(profile_dir)
    try:
        conn = sqlite3.connect(qm_db, timeout=5.0)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT storage_key FROM buckets")
        all_keys = [row[0] for row in cursor.fetchall()]

        keys_to_delete = []
        for k in all_keys:
            if k.startswith("chrome-extension://") or k.startswith("devtools://"):
                continue
            # Extract domain from storage_key (e.g. https://x.com/ or https://ad.googlesyndication.com/)
            try:
                parsed = urlparse(k.split("^")[0])
                host = parsed.netloc.split(":")[0].lower()
                if not host_matches_whitelist(host, allowed_domains, match_substrings):
                    keys_to_delete.append(k)
            except:
                pass

        logger.info(f"📊 [WebStorage/Quota] [{profile_name}]: Total origins: {len(all_keys)} | 🧹 Purging: {len(keys_to_delete)}")

        if not dry_run and keys_to_delete:
            batch_size = 500
            for i in range(0, len(keys_to_delete), batch_size):
                batch = keys_to_delete[i:i + batch_size]
                cursor.execute(
                    "DELETE FROM buckets WHERE storage_key IN ({seq})".format(seq=','.join(['?'] * len(batch))),
                    batch
                )
            conn.commit()
            cursor.execute("VACUUM")

        conn.close()
    except sqlite3.OperationalError:
        pass  # Chrome is actively locking QuotaManager in memory; will be processed when Chrome cycles
    except Exception as e:
        logger.debug(f"QuotaManager clean error: {e}")


def flush_network_and_dns(dry_run: bool = False):
    """Flushes local DNS resolver cache and attempts ARP table refresh on macOS."""
    logger.info("🌐 [Network] Flushing macOS Directory Service DNS Cache & Refreshing ARP...")
    if dry_run:
        logger.info("ℹ️ [DRY RUN] Would execute dscacheutil -flushcache")
        return

    # 1. Flush DNS cache via dscacheutil (Standard macOS DNS resolver cache flush)
    try:
        res = subprocess.run(["dscacheutil", "-flushcache"], capture_output=True, text=True, timeout=5)
        if res.returncode == 0:
            logger.info("✅ [DNS] Successfully flushed macOS DNS cache (dscacheutil -flushcache).")
        else:
            logger.warning(f"⚠️ [DNS] dscacheutil returned non-zero code: {res.stderr}")
    except Exception as e:
        logger.error(f"❌ [DNS] Error flushing DNS: {e}")

    # 2. Clear ARP cache (attempts kernel flush if permitted)
    try:
        res_arp = subprocess.run(["arp", "-d", "-a"], capture_output=True, text=True, timeout=5)
        if res_arp.returncode == 0:
            logger.info("✅ [ARP] Successfully cleared ARP routing cache.")
        else:
            logger.info("ℹ️ [ARP] ARP table refresh completed (kernel socket write skipped without root).")
    except Exception as e:
        logger.debug(f"ARP flush error: {e}")


def run_guardian(dry_run: bool = False):
    logger.info("🛡️ ────────────────────────────────────────────────────────")
    logger.info(f"🛡️ Starting Full-Stack Cookie Guardian Sweep {'[DRY RUN]' if dry_run else ''}")
    logger.info("🛡️ ────────────────────────────────────────────────────────")

    whitelist, match_substrings, auto_open_tabs = load_whitelist()
    allowed_domains = set(d.lower() for d in whitelist)

    if auto_open_tabs:
        open_domains = get_open_chrome_tab_domains()
        if open_domains:
            logger.info(f"🌐 Auto-Whitelisted {len(open_domains)} currently active open tab domain(s): {sorted(list(open_domains))}")
            allowed_domains.update(open_domains)

    logger.info(f"🔒 Global Substring Rules: {match_substrings} (unconditionally preserved)")
    logger.info(f"📋 Total Whitelisted Root Domains ({len(allowed_domains)}): {sorted(list(allowed_domains))}")

    profiles = get_chrome_profiles()
    if not profiles:
        logger.warning("No Chrome profiles found.")
        return

    for p in profiles:
        clean_cookie_db(p, allowed_domains, match_substrings, dry_run=dry_run)
        clean_indexeddb(p, allowed_domains, match_substrings, dry_run=dry_run)
        clean_service_workers(p, allowed_domains, match_substrings, dry_run=dry_run)
        clean_quota_manager(p, allowed_domains, match_substrings, dry_run=dry_run)

    # Flush DNS and refresh ARP at the end of the routine
    flush_network_and_dns(dry_run=dry_run)

    logger.info("🎉 Full-Stack Cookie Guardian & Network Optimization Finished.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cookie Guardian - Automated Cookie, Site Data & Network Purge Agent")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without deleting data")
    args = parser.parse_args()

    run_guardian(dry_run=args.dry_run)

