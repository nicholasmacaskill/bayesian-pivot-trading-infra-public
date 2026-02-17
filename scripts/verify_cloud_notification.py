import modal
from src.core.config import Config
from src.clients.telegram_notifier import TelegramNotifier
import os

# Define a minimal image
image = (
    modal.Image.debian_slim()
    .pip_install("requests")
    .add_local_dir("src", remote_path="/root/src")
)

app = modal.App("verify-notification")

@app.function(
    image=image,
    secrets=Config.get_modal_secrets()
)
def test_cloud_notification():
    print("🚀 Testing Cloud Notification...")
    
    # Check Env Vars
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    masked_token = f"{token[:5]}...{token[-5:]}" if token else "None"
    masked_chat = f"{chat_id[:2]}...{chat_id[-2:]}" if chat_id else "None"
    
    print(f"🔑 Token available: {masked_token}")
    print(f"🆔 Chat ID available: {masked_chat}")
    
    if not token or not chat_id:
        print("❌ Missing Credentials in Cloud Environment!")
        return
        
    try:
        notifier = TelegramNotifier()
        notifier._send_message("🔔 This is a **Cloud Test Message** from the investigation script.")
        print("✅ Message sent successfully!")
    except Exception as e:
        print(f"❌ Failed to send message: {e}")

if __name__ == "__main__":
    with app.run():
        test_cloud_notification.call()
