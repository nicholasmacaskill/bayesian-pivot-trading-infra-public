import sys
import os
import subprocess
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clients.telegram_notifier import TelegramNotifier

def main():
    load_dotenv('.env.local')
    notifier = TelegramNotifier()
    lock_file = "/tmp/scanner_watchdog_alerted.lock"
    
    # Check if local_scanner.py is running
    try:
        # We use ps and grep to be more robust than pgrep in some environments
        output = subprocess.check_output("ps aux | grep -i 'src/runners/local_scanner.py' | grep -v grep", shell=True).decode('utf-8')
        if output.strip():
            # It's running, clear the lock file if it exists so it can alert again next time it crashes
            if os.path.exists(lock_file):
                os.remove(lock_file)
            return
    except subprocess.CalledProcessError:
        # If grep finds nothing, it returns exit code 1, triggering this exception
        pass
    
    # If we got here, it's not running. Check lock file to avoid spamming alerts every 5 minutes.
    if os.path.exists(lock_file):
        return
    
    # Send alert
    msg = (
        "🚨 <b>CRITICAL SYSTEM ALERT</b> 🚨\n\n"
        "Your Bayesian Pivot Local Scanner has unexpectedly stopped running or crashed!\n\n"
        "Please restart it as soon as possible."
    )
    notifier._send_message(msg)
    
    # Create lock file
    with open(lock_file, "w") as f:
        f.write("alerted")

if __name__ == "__main__":
    main()
