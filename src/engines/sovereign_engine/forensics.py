
import os
import sqlite3
import shutil
import tempfile
import logging
from datetime import datetime, timezone, timedelta
from . import patterns

def scan_browser_history():
    """
    Scans browser history for known infostealer domains.
    Returns: list of threats
    """
    threats = []
    # Common browser history locations on macOS
    history_paths = {
        'Chrome': os.path.expanduser('~/Library/Application Support/Google/Chrome/Default/History'),
        'Brave': os.path.expanduser('~/Library/Application Support/BraveSoftware/Brave-Browser/Default/History'),
        'Arc': os.path.expanduser('~/Library/Application Support/Arc/User Data/Default/History'),
        'Edge': os.path.expanduser('~/Library/Application Support/Microsoft Edge/Default/History')
    }

    # Simple list of known bad domains (REDACTED/Simplified for this context)
    # In a real scenario, this would check against a larger threat intel database
    SUSPICIOUS_DOMAINS = [
        'download-installer.com', 'drivers-update-center.net', 
        'support-microsoft-alert.org', 'auth-verify-account.net'
    ]

    for browser, path in history_paths.items():
        if not os.path.exists(path):
            continue
            
        try:
            # Copy to temp file to avoid locking issues if browser is open
            with tempfile.NamedTemporaryFile(delete=False) as tmp_db:
                shutil.copy2(path, tmp_db.name)
                
                conn = sqlite3.connect(tmp_db.name)
                cursor = conn.cursor()
                
                # Query last 7 days of history
                # Chrome stores time as microseconds since 1601-01-01
                # Simplified query for recent URLs
                cursor.execute("SELECT url, title, last_visit_time FROM urls ORDER BY last_visit_time DESC LIMIT 500")
                
                for row in cursor.fetchall():
                    url = row[0]
                    title = row[1]
                    
                    if any(bad in url for bad in SUSPICIOUS_DOMAINS):
                        threats.append({
                            "type": "MALICIOUS_DOMAIN",
                            "severity": "HIGH",
                            "title": "🚨 DISCOVERED MALICIOUS HISTORY",
                            "summary": f"Visited known malicious site in {browser}: {title}",
                            "url": url,
                            "browser": browser
                        })
                
                conn.close()
                os.unlink(tmp_db.name)
                
        except Exception as e:
            logging.debug(f"Failed to scan {browser} history: {e}")
            
    return threats

def check_browser_persistence():
    """
    Checks for browser persistence mechanisms like Service Workers.
    Returns: (safe_list, threat_list)
    """
    threats = []
    safe = []
    
    # Locations for Service Workers / Local Storage
    sw_paths = {
        'Chrome': os.path.expanduser('~/Library/Application Support/Google/Chrome/Default/Service Worker/'),
        'Brave': os.path.expanduser('~/Library/Application Support/BraveSoftware/Brave-Browser/Default/Service Worker/'),
    }
    
    for browser, path in sw_paths.items():
        if not os.path.exists(path):
            continue
            
        # In a real implementation this would parse the LevelDB
        # For this recovery, we just check existence and modified times
        try:
            for root, dirs, files in os.walk(path):
                for file in files:
                    if file == 'LOCK': continue
                    full_path = os.path.join(root, file)
                    # Simple heuristic: heavily modified SW folders might indicate activity
                    # This is a placeholder for the deep LevelDB parsing
                    pass
        except Exception:
            pass
            
    return safe, threats

def get_attacker_ip(threat_event):
    """
    Extracts attacker IP from a threat event if available.
    """
    if not threat_event:
        return None
    return threat_event.get('remote_ip')

def audit_clipboard_hijacker():
    """
     audits the clipboard for signs of hijacking (crypto address swapping, etc).
    """
    # Placeholder for forensic audit logic
    return []

def resolve_domain_with_timeout(domain, timeout=2):
    """
    Resolves a domain to an IP with a short timeout.
    """
    try:
        # Simple placeholder
        return "0.0.0.0" 
    except:
        return None
