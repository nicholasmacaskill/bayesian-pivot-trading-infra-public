import sys
import os
import logging

# Add project root to path
SMC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, SMC_ROOT)

try:
    from src.engines.sovereign_engine import forensics, scanners
except ImportError:
    print("❌ Critical: sovereign_engine not found. Ensure you are running from the SMC root.")
    sys.exit(1)

# Setup simple logging
logging.basicConfig(level=logging.ERROR)

def run_forensic_audit():
    print("🔎 STARTING DEEP FORENSIC AUDIT...")
    print("--------------------------------")
    
    threats_found = False
    
    # 1. Check Browser History for Infostealer Domains
    print("\n[1/4] Scanning Browser History for known Stealer Domains...")
    history_threats = forensics.scan_browser_history()
    if history_threats:
        threats_found = True
        for t in history_threats:
            print(f"  🚨 MATCH: {t['summary']}")
            print(f"     URL: {t.get('url', 'N/A')}")
    else:
        print("  ✅ No known infostealer domains found in history.")

    # 2. Check Browser Persistence
    print("\n[2/4] Scanning for 'Shadow Persistence' (Service Workers)...")
    _, persistence_threats = forensics.check_browser_persistence()
    if persistence_threats:
        threats_found = True
        for t in persistence_threats:
            print(f"  🚨 SUSPICIOUS: {t['summary']}")
            print(f"     Path: {t.get('path', 'N/A')}")
    else:
        print("  ✅ No suspicious Service Workers detected.")

    # 3. Check Extensions
    print("\n[3/4] Scanning Browser Extensions...")
    extension_threats = scanners.scan_extensions()
    if extension_threats:
        threats_found = True
        for t in extension_threats:
            print(f"  🚨 RISK: {t['name']} ({t['id']})")
            print(f"     Path: {t.get('path', 'N/A')}")
            print(f"     Risks: {t['risks']}")
    else:
        print("  ✅ No high-risk extensions found.")

    # 4. Check Root CAs
    print("\n[4/4] Scanning Root Certificates (Keychains)...")
    ca_threats = scanners.scan_root_cas()
    if ca_threats:
        threats_found = True
        for t in ca_threats:
            print(f"  🚨 ROGUE CA: {t['subject']}")
            print(f"     Keychain: {t['keychain']}")
    else:
        print("  ✅ No rogue Root CAs found.")

    print("\n--------------------------------")
    if threats_found:
        print("⚠️  POTENTIAL COMPROMISE INDICATORS FOUND.")
    else:
        print("✅  Clean forensic scan. No obvious indicators of compromise found.")

if __name__ == "__main__":
    run_forensic_audit()
