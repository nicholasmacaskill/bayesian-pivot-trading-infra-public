import os
import sys
import time
import subprocess
import threading

# ── SMC-native path helper (replaces path_utils) ────────────────────────────────────────────────
SMC_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
def _run(f):    os.makedirs(os.path.join(SMC_ROOT, 'run_data'), exist_ok=True); return os.path.join(SMC_ROOT, 'run_data', f)

# TRIGGER SYSTEM (Using project run directory)
TRIGGER_RESTART = _run('.trigger_restart')
TRIGGER_LOCKDOWN = _run('.trigger_lockdown')
TRIGGER_BOOTSTRAP = _run('.trigger_bootstrap')

def check_triggers_loop():
    """Background thread to catch UI signals instantly."""
    while True:
        try:
            if os.path.exists(TRIGGER_RESTART):
                time.sleep(0.2)
                print("[!] REMOTE RESTART SIGNAL RECEIVED")
                os.remove(TRIGGER_RESTART)
                script_path = os.path.join(SMC_ROOT, "src", "engines", "guard_engine.py")
                os.execv(sys.executable, [sys.executable, script_path])
                
            if os.path.exists(TRIGGER_LOCKDOWN):
                print("[!] REMOTE LOCKDOWN SIGNAL RECEIVED")
                os.remove(TRIGGER_LOCKDOWN)
                browsers = ["Google Chrome", "Safari", "Firefox", "Brave Browser", "Arc", "Microsoft Edge"]
                for b in browsers:
                    subprocess.run(["/usr/bin/pkill", "-f", b], check=False)
                    time.sleep(1)
                    subprocess.run(["/usr/bin/pkill", "-9", "-f", b], check=False)
                    subprocess.run(["osascript", "-e", f'tell application "{b}" to quit'], check=False)
                
            if os.path.exists(TRIGGER_BOOTSTRAP):
                print("[!] REMOTE BOOTSTRAP SIGNAL RECEIVED")
                os.remove(TRIGGER_BOOTSTRAP)
                bootstrap_path = os.path.join(SMC_ROOT, "tools", "bootstrap_discovery.py")
                if os.path.exists(bootstrap_path):
                    subprocess.Popen([sys.executable, bootstrap_path])
                else:
                    print(f"Error: {bootstrap_path} not found.")
        except Exception as e:
            print(f"Trigger Loop Error: {e}")
        time.sleep(0.5)

def start_trigger_thread():
    t = threading.Thread(target=check_triggers_loop, daemon=True)
    t.start()
    print("[+] Sovereign Trigger Listener Active.")

def check_triggers():
    """Obsolete but kept for signature compatibility."""
    pass
