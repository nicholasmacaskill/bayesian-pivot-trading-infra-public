#!/usr/bin/env python3
"""
sovereign_ctl.py — CLI control interface for Sovereign Guard
Usage: python src/runners/sovereign_ctl.py {start|stop|status|scan|logs|dev|secure|sessions}

NOTE: This was ported from python-sovereign-guard.
path_utils / sovereign_core are replaced with SMC-native equivalents.
"""
import sys
import os
import subprocess
import time
import signal
from datetime import datetime, timezone

# ── SMC-compatible path helpers (replaces path_utils) ────────────────────────
SMC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def _run_dir():   return os.path.join(SMC_ROOT, 'run_data')
def _log_dir():   return os.path.join(SMC_ROOT, 'logs')
def _get_run(f):  os.makedirs(_run_dir(), exist_ok=True); return os.path.join(_run_dir(), f)
def _get_log(f):  os.makedirs(_log_dir(), exist_ok=True); return os.path.join(_log_dir(), f)

# Configuration
MONITOR_SCRIPT = os.path.join(SMC_ROOT, "src", "engines", "guard_watchdog.py")
PID_FILE       = _get_run("guard_supervisor.pid")
SAFE_MODE_FILE = _get_run("developer_mode.lock")
VENV_PYTHON    = os.path.join(SMC_ROOT, "venv", "bin", "python3")
ENV_FILE       = os.path.join(SMC_ROOT, ".env.sovereign")


def get_pid():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                return int(f.read().strip())
        except:
            return None
    return None

def is_running(pid):
    if pid is None: return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def authorize_action():
    """Enforces Hardware Key or Backup Code authorization."""
    is_enforced = False
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            for line in f:
                if line.startswith('RUBICON_ENFORCED='):
                    is_enforced = (line.split('=', 1)[1].strip().lower() == 'true')
                    break

    if not is_enforced: return True

    # Fallback: prompt for a simple passphrase stored in .env.sovereign
    secret = ''
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, 'r') as f:
            for line in f:
                if line.startswith('SOVEREIGN_SECRET='):
                    secret = line.split('=', 1)[1].strip()
                    break
    entered = input("🔒 Enter Sovereign Secret to proceed: ").strip()
    if entered == secret:
        print("✅ Authorized.")
        return True
    print("❌ ACCESS DENIED.")
    return False

def start():
    pid = get_pid()
    if is_running(pid):
        print(f"[-] Supervisor is already running (PID: {pid})")
        return

    print("[-] Starting Sovereign Guard (Watchdog Supervisor)...")
    try:
        out_log = _get_log("guard_watchdog.out")
        err_log = _get_log("guard_watchdog.err")
        with open(out_log, "a") as out, open(err_log, "a") as err:
            proc = subprocess.Popen([VENV_PYTHON, MONITOR_SCRIPT], stdout=out, stderr=err, stdin=subprocess.DEVNULL, cwd=SMC_ROOT)
        with open(PID_FILE, 'w') as f:
            f.write(str(proc.pid))
        print(f"[+] Sovereign Guard Supervisor started (PID: {proc.pid})\n    Logs: tail -f {out_log}")
    except Exception as e:
        print(f"[!] Failed to start supervisor: {e}")

def stop():
    if not authorize_action(): return
    pid = get_pid()
    if not is_running(pid):
        print("[-] Monitor is not running.")
        if os.path.exists(PID_FILE): os.remove(PID_FILE)
        return

    print(f"[-] Stopping Sovereign Guard (PID: {pid})...")
    try:
        # Kill the supervisor
        os.kill(pid, signal.SIGTERM)
        
        # Kill any orphaned monitors
        subprocess.run(["pkill", "-f", "guard_monitor.py"], capture_output=True)
        
        for _ in range(10):
            if not is_running(pid): break
            time.sleep(0.1)
        if os.path.exists(PID_FILE): os.remove(PID_FILE)
        print("[+] Sovereign Guard stopped and cleaned.")
    except Exception as e:
        print(f"[!] Stop failed: {e}")

def status():
    pid = get_pid()
    if is_running(pid):
        print(f"✅ Sovereign Guard: ACTIVE (PID: {pid})")
        if os.path.exists(SAFE_MODE_FILE):
            print("⚠️  Mode: DEVELOPER (Safe Mode Active)")
        else:
            try:
                from learning_engine import get_protection_mode, analyze_learnings
                mode = get_protection_mode()
                s = analyze_learnings()
                if mode == 'learn':
                    print(f"📘 Mode: LEARN (Day {s.get('days_elapsed', 0)+1}/7)\n    Observed: {s.get('total_observations', 0)} processes")
                else:
                    print(f"🛡️  Mode: {mode.upper()}")
            except:
                print("🛡️  Mode: SECURE")
    else:
        print("❌ Sovereign Guard: STOPPED")
    
    # Check for last forensic audit
    audit_log = _get_log("forensic_audit.log")
    if os.path.exists(audit_log):
        mtime = os.path.getmtime(audit_log)
        last_audit = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"🔎 Last Deep Audit: {last_audit}")

def dev_mode():
    if not authorize_action(): return
    secret = path_utils.get_secret()
    if not os.path.exists(SAFE_MODE_FILE):
        with open(SAFE_MODE_FILE, 'w') as f: f.write(secret or "")
        print("⚠️  [DEVELOPER MODE ENABLED]")
        print("[-] Playwright/Puppeteer whitelisted for non-primary browser profiles.")
        print("[-] To unseal Port 9222 for debugging, run: sudo pfctl -a com.sovereign.guard -F rules")
    else:
        print("[-] Already in Developer Mode.")

def deep_audit():
    """Executes the modern forensic audit script."""
    print("🚀 Initializing Deep Forensic Audit...")
    audit_script = os.path.join(SMC_ROOT, "src", "runners", "forensic_audit.py")
    audit_log = _get_log("forensic_audit.log")
    
    try:
        # We run it and pipe to a log for the status command to see
        with open(audit_log, "w") as f:
            subprocess.check_call([VENV_PYTHON, audit_script], stdout=sys.stdout, stderr=sys.stderr)
            # Touching the log to update mtime even if stdout is redirected
            os.utime(audit_log, None)
    except subprocess.CalledProcessError as e:
        print(f"❌ Audit failed with exit code {e.returncode}")
    except Exception as e:
        print(f"❌ Error running audit: {e}")

def secure_mode():
    if os.path.exists(SAFE_MODE_FILE):
        os.remove(SAFE_MODE_FILE)
        print("🛡️  [SECURE MODE ENABLED]")
        print("[+] Re-sealing Port 9222...")
        try:
            subprocess.run(['sudo', 'pfctl', '-a', 'com.sovereign.guard', '-f', '/etc/pf.anchors/com.sovereign.guard'], check=False)
            print("🔒 Port 9222 is sealed.")
        except:
            print("⚠️  Failed to re-seal Port 9222 automatically. Run: sudo ./fix_firewall.sh")
    else:
        print("[-] Already in Secure Mode.")

def scan_now():
    print("🔍 Scanning all active processes via GuardEngine...")
    # Add SMC root to path
    sys.path.insert(0, SMC_ROOT)
    try:
        from src.engines.guard_engine import GuardEngine
        g = GuardEngine()
        # Run a synchronous snapshot (no thread)
        proc_threats  = g._scan_processes()
        ca_threats    = g._scan_root_cas()
        ext_threats   = g._scan_extensions()
        persist_threats = g._check_persistence()
        all_threats = proc_threats + ca_threats + ext_threats + persist_threats

        if all_threats:
            print(f"\n\u274c THREATS DETECTED: {len(all_threats)}")
            for t in all_threats:
                print(f"  [{t.get('severity','?')}] {t.get('title','?')}")
                print(f"       {t.get('summary','')}")
            sys.exit(1)
        else:
            print(f"\n\u2705 SECURE: No active threats found. Trust score: {g.get_trust_score()}/100")
    except Exception as e:
        print(f"[!] Scan failed: {e}")

def setup_2fa():
    print("🔐 SOVEREIGN GUARD // 2FA SETUP")
    print("[i] 2FA setup is managed via the .env.sovereign file.")
    print("    Set RUBICON_ENFORCED=true and SOVEREIGN_SECRET=<your-passphrase> to enable.")

def bootstrap():
    """Runs the bootstrap system discovery tool."""
    if not authorize_action(): return
    print("🚀 SOVEREIGN GUARD // BOOTSTRAP")
    
    script_path = os.path.join(path_utils.get_project_root(), "tools", "bootstrap_discovery.py")
    if not os.path.exists(script_path):
        print(f"[!] Bootstrap script not found at: {script_path}")
        return

    try:
        subprocess.check_call([VENV_PYTHON, script_path])
    except subprocess.CalledProcessError as e:
        print(f"[!] Bootstrap failed: {e}")
    except OSError as e:
        print(f"[!] Execution failed: {e}")

        
def view_logs():
    """Views today's security alerts"""
    log_file = _get_log('guard_engine.log')
    today = datetime.now().strftime('%Y-%m-%d')
    print(f"📊 SEARCHING ALERTS FOR: {today}")
    print("=" * 50)
    
    if os.path.exists(log_file):
        found = False
        with open(log_file, 'r') as f:
            for line in f:
                if today in line and any(x in line for x in ["THREAT", "SUSPICIOUS", "CRITICAL", "NEUTRALIZED"]):
                    print(line.strip())
                    found = True
        if not found:
            print("   [i] No critical alerts detected today.")
    else:
        print("   [!] Log file not found.")

def clean_logs():
    """Removes all log and error files."""
    logs = ["guard_engine.log", "guard_watchdog.out", "guard_monitor.out", "guard_monitor.err", "guard_watchdog.err"]
    for l in logs:
        path = _get_log(l)
        if os.path.exists(path):
            os.remove(path)
    print("🧹 Logs cleaned.")

def dashboard():
    """Displays the Sovereign Guard Dashboard."""
    print("📊 Opening Dashboard...")
    try:
        script_path = os.path.join(path_utils.get_project_root(), "src", "sovereign_dashboard.py")
        subprocess.Popen([VENV_PYTHON, script_path])
    except Exception as e:
        print(f"[!] Failed to launch dashboard: {e}")

def sessions():
    """Reviews session domains learned from browser activity."""
    print("🔍 SOVEREIGN GUARD // SESSION DOMAIN REVIEW")
    try:
        sys.path.insert(0, SMC_ROOT)
        from src.engines.guard_session import print_session_review
        print_session_review()
    except (ImportError, AttributeError):
        print("[i] Session domain review: check guard_engine logs for SESSION_HIJACK_RISK events.")

def report():
    """Generates a security report."""
    print("📋 Generating Security Report...")
    # Logic for generating report could be added here
    print("[i] Report feature coming soon or check logs via ./sovereign logs")

def uninstall_wizard():
    """Guides user through uninstallation."""
    print("🗑️ Sovereign Guard Uninstall Wizard")
    confirm = input("Confirm uninstallation? (y/N): ")
    if confirm.lower() == 'y':
        # Logic for uninstalling
        print("[!] Logic for uninstallation would be implemented here.")

def main():
    COMMANDS = {
        'start': start, 'stop': stop, 'status': status, 'dev': dev_mode,
        'secure': secure_mode, 'scan': scan_now, '2fa': setup_2fa,
        'restart': lambda: (stop(), time.sleep(1), start()),
        'logs': view_logs,
        'bootstrap': bootstrap,
        'clean': clean_logs,
        'dashboard': dashboard,
        'report': report,
        'sessions': sessions,
        'uninstall': uninstall_wizard,
        'audit': deep_audit
    }
    
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: ./sovereign {{{'|'.join(COMMANDS.keys())}}}")
        sys.exit(1)
        
    COMMANDS[sys.argv[1]]()

if __name__ == "__main__":
    main()
