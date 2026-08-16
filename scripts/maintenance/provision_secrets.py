import subprocess
import os

# Values sourced from your .env.local
from dotenv import load_dotenv
load_dotenv(".env.local")

# Map of Secret Name -> Env Var Name (or default value)
# We want to ensure we capture the keys exactly as needed by the app.
# Base Secrets
secrets = {
    "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY"),
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID"),
    "CRYPTOPANIC_API_KEY": os.getenv("CRYPTOPANIC_API_KEY"),
    "WHALE_ALERT_API_KEY": os.getenv("WHALE_ALERT_API_KEY", "SKIP"),
    "SYNC_AUTH_KEY": os.getenv("SYNC_AUTH_KEY"),
}

# Dynamically pull all TRADELOCKER_* env vars (Account A, B, C, etc.)
for k, v in os.environ.items():
    if k.startswith("TRADELOCKER_") and v:
        secrets[k] = v

# Ensure Account A fallbacks if TRADELOCKER_EMAIL_A is not explicitly set
if "TRADELOCKER_EMAIL_A" not in secrets and os.getenv("TRADELOCKER_EMAIL"):
    secrets["TRADELOCKER_EMAIL_A"] = os.getenv("TRADELOCKER_EMAIL")
    secrets["TRADELOCKER_PASSWORD_A"] = os.getenv("TRADELOCKER_PASSWORD")
    secrets["TRADELOCKER_SERVER_A"] = os.getenv("TRADELOCKER_SERVER")
    secrets["TRADELOCKER_BASE_URL_A"] = os.getenv("TRADELOCKER_BASE_URL")


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
