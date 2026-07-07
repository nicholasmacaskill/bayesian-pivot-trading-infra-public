import subprocess
import os

# Values sourced from your .env.local
from dotenv import load_dotenv
load_dotenv(".env.local")

# Map of Secret Name -> Env Var Name (or default value)
# We want to ensure we capture the keys exactly as needed by the app.
secrets = {
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),
    "CRYPTOPANIC_API_KEY": os.getenv("CRYPTOPANIC_API_KEY"),
    "WHALE_ALERT_API_KEY": os.getenv("WHALE_ALERT_API_KEY", "SKIP"),
    "SYNC_AUTH_KEY": os.getenv("SYNC_AUTH_KEY"),
    
    # Account A (Primary)
    "TRADELOCKER_EMAIL_A": os.getenv("TRADELOCKER_EMAIL_A") or os.getenv("TRADELOCKER_EMAIL"),
    "TRADELOCKER_PASSWORD_A": os.getenv("TRADELOCKER_PASSWORD_A") or os.getenv("TRADELOCKER_PASSWORD"),
    "TRADELOCKER_SERVER_A": os.getenv("TRADELOCKER_SERVER_A") or os.getenv("TRADELOCKER_SERVER"),
    "TRADELOCKER_BASE_URL_A": os.getenv("TRADELOCKER_BASE_URL_A") or os.getenv("TRADELOCKER_BASE_URL"),
    
    # Account B (Secondary)
    "TRADELOCKER_EMAIL_B": os.getenv("TRADELOCKER_EMAIL_B"),
    "TRADELOCKER_PASSWORD_B": os.getenv("TRADELOCKER_PASSWORD_B"),
    "TRADELOCKER_SERVER_B": os.getenv("TRADELOCKER_SERVER_B"),
    "TRADELOCKER_BASE_URL_B": os.getenv("TRADELOCKER_BASE_URL_B") or os.getenv("TRADELOCKER_BASE_URL_A") or os.getenv("TRADELOCKER_BASE_URL")
}

# Construct the command
cmd = ["./venv/bin/modal", "secret", "create", "smc-secrets", "--force"]
for k, v in secrets.items():
    cmd.append(f"{k}={v}")

print("🚀 Uploading secrets to Modal (smc-secrets)...")
try:
    subprocess.run(cmd, check=True)
    print("✅ Secrets configured successfully!")
except subprocess.CalledProcessError as e:
    print(f"❌ Error uploading secrets: {e}")
