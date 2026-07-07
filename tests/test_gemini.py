import os
from google import genai

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ No API Key found in environment.")
else:
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model='gemini-2.0-flash', contents="Say 'AI Active'")
        print(f"✅ Response: {response.text}")
    except Exception as e:
        print(f"❌ Gemini Error: {e}")
