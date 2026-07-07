import os
import ccxt
from src.core.config import Config
import yfinance as yf
from google import genai
from supabase import create_client

def verify_vitals():
    """
    Forensic Vitals Check: Ensures all production dependencies are responsive.
    Returns a status report dictionary.
    """
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
        hist = ticker.history(period="5d")
        if not hist.empty:
            report["checks"]["Intermarket (YF)"] = "✅ Connected"
        else:
            raise ValueError("Empty data returned")
    except Exception as e:
        report["checks"]["Intermarket (YF)"] = "❌ Failed"
        report["issues"].append(f"YFinance Intermarket: {str(e)}")
        report["status"] = "DEGRADED"

    # 3. Check AI Infrastructure (SovereignAIHub)
    try:
        from src.engines.ai_hub import SovereignAIHub
        hub = SovereignAIHub()
        if not hub.has_ai:
            raise ValueError("No AI providers configured")
            
        # Light connection probe to active provider
        if hub.together_client:
            # Probe Together AI
            hub.together_client.chat.completions.create(
                model=hub.together_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            report["checks"][f"AI Validator (Together/{hub.together_model})"] = "✅ Connected"
        elif hub.openrouter_client:
            # Probe OpenRouter
            hub.openrouter_client.chat.completions.create(
                model=hub.openrouter_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            report["checks"][f"AI Validator (OpenRouter/{hub.openrouter_model})"] = "✅ Connected"
        elif hub.gemini_client:
            # Probe Gemini
            hub.gemini_client.models.generate_content(
                model='gemini-2.5-flash', 
                contents="ping",
                config={'http_options': {'timeout': 15}}
            )
            report["checks"]["AI Validator (Gemini)"] = "✅ Connected"
        elif hub.anthropic_client:
            # Probe Anthropic
            hub.anthropic_client.messages.create(
                model="claude-3-5-sonnet-20240620",
                max_tokens=5,
                messages=[{"role": "user", "content": "ping"}]
            )
            report["checks"]["AI Validator (Claude)"] = "✅ Connected"
        elif hub.openai_client:
            # Probe OpenAI
            hub.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5
            )
            report["checks"]["AI Validator (GPT)"] = "✅ Connected"
        else:
            report["checks"]["AI Validator (Local)"] = "✅ Offline Active"
    except Exception as e:
        report["checks"]["AI Validator"] = f"❌ Failed ({str(e)})"
        report["issues"].append(f"AI API Connectivity: {str(e)}")
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
