import os
import requests
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local")

def check_telegram():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN is missing in .env")
        return
    if not chat_id:
        print("❌ TELEGRAM_CHAT_ID is missing in .env")
        return
        
    print("✅ Telegram credentials found in environment.")
    
    # Check Bot Info
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if data.get("ok"):
            print(f"✅ Bot is valid: {data['result']['username']}")
        else:
            print(f"❌ Bot token is invalid: {data}")
    except Exception as e:
        print(f"❌ Failed to connect to Telegram API: {e}")
        
    # Check Chat ID (by sending a silent test message)
    # We won't send a real message to avoid spam, but we can't easily verify chat_id without sending.
    # getChat method might work if the bot is admin or has history.
    
    url = f"https://api.telegram.org/bot{token}/getChat"
    try:
        resp = requests.post(url, json={"chat_id": chat_id}, timeout=5)
        data = resp.json()
        if data.get("ok"):
            print(f"✅ Chat ID is valid: {data['result'].get('title', 'Private Chat')}")
        else:
            print(f"❌ Chat ID might be invalid or bot is not a member: {data}")
    except Exception as e:
        print(f"❌ Failed to check Chat ID: {e}")

if __name__ == "__main__":
    check_telegram()
