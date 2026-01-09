import subprocess
import os

# Values sourced from your .env.local
secrets = {
    "GEMINI_API_KEY": "REDACTED_GOOGLE_API_KEY",
    "TELEGRAM_BOT_TOKEN": "REDACTED_TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID": "7934081383",
    "CRYPTOPANIC_API_KEY": "REDACTED_CRYPTOPANIC_KEY",
    "WHALE_ALERT_API_KEY": "SKIP",
    "SYNC_AUTH_KEY": "REDACTED_SYNC_KEY",
    # Account A
    "TRADELOCKER_EMAIL_A": "1h3w4hp7ld@upcomers.com",
    "TRADELOCKER_PASSWORD_A": "REDACTED_PASSWORD",
    "TRADELOCKER_SERVER_A": "UPCOMS",
    "TRADELOCKER_BASE_URL_A": "https://demo.tradelocker.com",
    # Account B
    "TRADELOCKER_EMAIL_B": "5pys8ajue0@upcomers.com",
    "TRADELOCKER_PASSWORD_B": "REDACTED_PASSWORD",
    "TRADELOCKER_SERVER_B": "UPCOMS",
    "TRADELOCKER_BASE_URL_B": "https://demo.tradelocker.com"
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
