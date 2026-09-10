#!/usr/bin/env python3
"""
🔄 Cookie Guardian Restore Tool
Instantly restores the most recent Chrome cookie backup.
"""

import os
import sys
import glob
import shutil
import logging

BACKUP_DIR = os.path.join(os.path.expanduser("~"), ".cookie_guardian", "backups")
CHROME_BASE = os.path.expanduser("~/Library/Application Support/Google/Chrome")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CookieRestore")

def restore_latest_backup():
    if not os.path.exists(BACKUP_DIR):
        logger.error(f"Backup directory {BACKUP_DIR} does not exist.")
        return

    # Find all backup files
    backups = sorted(glob.glob(os.path.join(BACKUP_DIR, "Cookies_*.db")), key=os.path.getmtime, reverse=True)
    if not backups:
        logger.error("No backups found.")
        return

    latest = backups[0]
    filename = os.path.basename(latest)
    # Filename format: Cookies_<profile>_<timestamp>.db
    parts = filename.split("_")
    profile = parts[1] if len(parts) >= 3 else "Default"

    target_cookie_db = os.path.join(CHROME_BASE, profile, "Cookies")
    if not os.path.exists(os.path.dirname(target_cookie_db)):
        logger.error(f"Target profile directory {os.path.dirname(target_cookie_db)} does not exist.")
        return

    logger.info(f"🔄 Restoring from: {latest}")
    logger.info(f"🎯 Target file:    {target_cookie_db}")

    try:
        shutil.copy2(latest, target_cookie_db)
        logger.info("✅ Restore complete! Restart Chrome to reload restored session tokens.")
    except Exception as e:
        logger.error(f"❌ Failed to restore backup: {e}")

if __name__ == "__main__":
    restore_latest_backup()
