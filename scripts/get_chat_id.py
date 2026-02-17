
import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(".env.local")

async def get_chat_id():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env.local")
        return

    bot = Bot(token)
    try:
        me = await bot.get_me()
        print(f"🤖 Connected successfully to bot: @{me.username}")
        print(f"👉 Please ensure you are messaging @{me.username}")

        print(f"Checking updates...")
        updates = await bot.get_updates()
        
        if not updates:
            print("📭 No messages found. Please send a message (e.g., 'Hello') to your bot in Telegram and run this script again.")
            return

        # Get the chat ID from the most recent message
        chat_id = updates[-1].message.chat.id
        user = updates[-1].message.from_user.username
        
        print(f"\n✅ Found Message from @{user}!")
        print(f"🆔 YOUR CHAT ID: {chat_id}")
        print("\nAdding this to your .env.local automatically...")
        
        # Append to .env.local
        with open(".env.local", "a") as f:
            f.write(f"\nTELEGRAM_CHAT_ID={chat_id}")
            
        print("🎉 Saved! You are ready to go.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(get_chat_id())
