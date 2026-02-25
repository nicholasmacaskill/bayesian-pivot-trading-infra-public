import os
from google import genai
from dotenv import load_dotenv

# Explicitly load .env.local
load_dotenv(".env.local")

api_key = os.environ.get("GEMINI_API_KEY")
print(f"Key found: {api_key[:10]}..." if api_key else "❌ No Key")

if api_key:
    try:
        client = genai.Client(api_key=api_key)
        # Using a model we know the user has access to
        response = client.models.generate_content(model='gemini-2.0-flash', contents="Test")
        print(f"✅ Gemini Response: {response.text}")
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
