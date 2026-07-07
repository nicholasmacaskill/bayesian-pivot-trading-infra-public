import os
from dotenv import load_dotenv
import sys

# Add root to sys.path
sys.path.append(os.getcwd())

from src.engines.smc_scanner import SMCScanner

def check_account():
    load_dotenv('.env.local')
    email = os.getenv('TRADELOCKER_EMAIL')
    print(f"Checking account: {email}")
    
    # Simple check to see if we can initialize and maybe fetch something
    try:
        # Note: SMCScanner might not have a direct balance method without execution engine
        # but let's see if we can at least verify credentials via a dummy call if possible.
        # Most scripts use the config.
        from src.core.config import Config
        config = Config()
        print("Config loaded successfully.")
        
        # If there's an execution engine, we'd use that. 
        # Let's check for a trade ledger or similar.
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_account()
