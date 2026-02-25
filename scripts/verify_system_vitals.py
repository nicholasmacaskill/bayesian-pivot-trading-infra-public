import os
import sys
import ccxt
import yfinance as yf
import google.generativeai as genai
from supabase import create_client
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import Config

def verify_vitals():
    """
    Forensic Vitals Check: Ensures all production dependencies are responsive.
    Returns a status report dictionary.
    """
    load_dotenv(".env")
    load_dotenv(".env.local")
    
    report = {
        "status": "HEALTHY",
        "issues": [],
        "checks": {}
    }

    # 1. Check Binance (CCXT)
    try:
        exchange = ccxt.binance()
        exchange.fetch_ticker('BTC/USDT')
        report["checks"]["Binance"] = "✅ Connected"
    except Exception as e:
        report["checks"]["Binance"] = "❌ Failed"
        report["issues"].append(f"Binance Connectivity: {str(e)}")
        report["status"] = "DEGRADED"

    # 2. Check YFinance (Intermarket)
    try:
        ticker = yf.Ticker("DX-Y.NYB")
        hist = ticker.history(period="1d")
        if not hist.empty:
            report["checks"]["Intermarket (YF)"] = "✅ Connected"
        else:
            raise ValueError("Empty data returned")
    except Exception as e:
        report["checks"]["Intermarket (YF)"] = "❌ Failed"
        report["issues"].append(f"YFinance Intermarket: {str(e)}")
        report["status"] = "DEGRADED"

    # 3. Check Gemini (AI Validator)
    try:
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("API Key missing")
        from google import genai
        client = genai.Client(api_key=api_key)
        # Lightweight probe
        response = client.models.generate_content(
            model='gemini-2.0-flash', 
            contents="ping"
        )
        if response.text:
            report["checks"]["AI Validator (Gemini)"] = "✅ Connected"
    except Exception as e:
        report["checks"]["AI Validator (Gemini)"] = f"❌ Failed ({str(e)})"
        report["issues"].append(f"Gemini API: {str(e)}")
        report["status"] = "DEGRADED"

    # 4. Check Supabase (Database)
    try:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
        if not url or not key:
            raise ValueError("Supabase credentials missing")
        supabase = create_client(url, key)
        # Simple query trace
        supabase.table("scans").select("id").limit(1).execute()
        report["checks"]["Database (Supabase)"] = "✅ Connected"
    except Exception as e:
        report["checks"]["Database (Supabase)"] = "❌ Failed"
        report["issues"].append(f"Supabase DB: {str(e)}")
        report["status"] = "DEGRADED"

    return report

if __name__ == "__main__":
    result = verify_vitals()
    print(f"System Status: {result['status']}")
    for check, status in result['checks'].items():
        print(f"{check}: {status}")
    if result['issues']:
        print("\n⚠️ Issues Detected:")
        for issue in result['issues']:
            print(f"- {issue}")
