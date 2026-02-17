import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv(".env.local")
api_key = os.environ.get("GEMINI_API_KEY")

if not api_key:
    print("❌ No API Key found.")
else:
    genai.configure(api_key=api_key)
    print("🔎 Listing Available Models...")
    print("🔎 Listing ALL Models...")
    try:
        for m in genai.list_models():
            print(f"   - {m.name} (Methods: {m.supported_generation_methods})")
            
        print("🧪 Testing Basic Generation...")
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content("test")
        print(f"✅ Generation Success: {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")
