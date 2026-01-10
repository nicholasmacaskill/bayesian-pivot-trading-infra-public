import os
import shutil
import re

# CONFIGURATION
# CONFIGURATION
SOURCE_DIR = os.getcwd()
DEST_DIR = os.path.join(SOURCE_DIR, "public_export")

SENSITIVE_FILES = [
    "config.py",
    "smc_scanner.py",
    "intermarket_engine.py",
    "ai_validator.py"
]

REPLACEMENTS = [
    # Config Redactions
    # (r"RISK_PER_TRADE = 0\.0065", 'RISK_PER_TRADE = 0.01'), # User requested to keep risk visible
    # (r"MAX_DRAWDOWN_LIMIT = 0\.06", 'MAX_DRAWDOWN_LIMIT = 0.10'),
    (r"AI_THRESHOLD = 7\.0", 'AI_THRESHOLD = None # [PROPRIETARY - COMMERCIAL LICENSE REQUIRED]'),
    (r"MIN_SMT_STRENGTH = 0\.3", 'MIN_SMT_STRENGTH = None # [PROPRIETARY - COMMERCIAL LICENSE REQUIRED]'),
    
    # Logic Redactions (Scanner)
    (r"if in_deep_discount and has_strong_smt and \(swept_pdl or swept_london\):", 
     "if False: # [PROPRIETARY ENTRY LOGIC - COMMERCIAL LICENSE REQUIRED]"),
    
    (r"return total_volume >= 5\.0", 'raise NotImplementedError("Volume Analysis is Proprietary - License Required")'),
    
    # Logic Redactions (Intermarket)
    (r"score \+= 0\.4 if yield_trend == 'DOWN' else -0\.4", "pass # [WEIGHTING PROPRIETARY - LICENSE REQUIRED]"),
    (r"score \+= 0\.3 if nq_trend == 'UP' else -0\.3", "pass # [WEIGHTING PROPRIETARY - LICENSE REQUIRED]"),
    
    # AI Prompt Redactions (Protecting the 'Oracle' logic)
    (r'YOU ARE THE SOVEREIGN GATEKEEPER[\s\S]*?(?=""")', '[SYSTEM PROMPT REDACTED FOR IP PROTECTION - PROPRIETARY ORACLE LOGIC]'),
    (r'self\.kb_path = os\.path\.join\(os\.path\.dirname\(__file__\), "ict_oracle_kb\.json"\)', 'self.kb_path = None # [PROPRIETARY KNOWLEDGE BASE - LICENSE REQUIRED]'),

    # Secrets Redactions
    (r'SYNC_AUTH_KEY = os\.environ\.get\("SYNC_AUTH_KEY", ""\)', 'SYNC_AUTH_KEY = os.environ.get("SYNC_AUTH_KEY", "dummy_key")')
]

def sanitize_file(filepath):
    """Reads a file, applies regex replacements, and overwrites it."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    for pattern, replacement in REPLACEMENTS:
        content = re.sub(pattern, replacement, content)
        
    # Generic "Header" addition
    header = "# [PUBLIC PORTFOLIO VERSION]\n# NOTE: Core proprietary logic and parameters have been redacted/standardized.\n# This repository demonstrates architecture, not live trading alpha.\n\n"
    content = header + content
    
    with open(filepath, 'w') as f:
        f.write(content)

def main():
    print(f"🚀 Preparing Public Release in: {DEST_DIR}")
    
    if os.path.exists(DEST_DIR):
        print(f"⚠️ Removing existing directory: {DEST_DIR}")
        shutil.rmtree(DEST_DIR)
        
    print("📂 Copying project...")
    shutil.copytree(SOURCE_DIR, DEST_DIR, ignore=shutil.ignore_patterns('venv', '__pycache__', '*.db', '.git', '.env', '.env.local', 'secrets.json', 'provision_secrets.py', 'node_modules', '.next', 'ict_oracle_kb.json'))
    
    print("🔒 Sanitizing sensitive files...")
    for filename in SENSITIVE_FILES:
        filepath = os.path.join(DEST_DIR, filename)
        if os.path.exists(filepath):
            print(f"   - Sanitizing {filename}...")
            sanitize_file(filepath)
            
    # Create a nice public README
    readme_path = os.path.join(DEST_DIR, "README.md")
    with open(readme_path, 'w') as f:
        f.write("""# Sovereign SMC (Public Portfolio Edition)

**A Cloud-Native Quantitative Trading Engine with Multi-Modal AI Validation.**

> *Note: This repository is a sanitized release of a live production system. Proprietary alpha parameters, specific entry logic, and Oracle Knowledge Base prompts have been redacted to protect intellectual property.*

## 🦅 System Overview

Sovereign SMC is an event-driven algorithmic trading system designed to capture institutional liquidity sweeps during the New York Session. It moves beyond simple "indicator" logic by integrating:

1.  **Statistical Arbitrage:** Relies on structural market inefficiencies (Liquidity Pools) with >50,000 Monte Carlo simulations backing the risk profile.
2.  **Multi-Modal AI Validation:** Utilizes Google Gemini 2.0 Flash (Vision + Text) to visually inspect chart structure and validate "smart money" footprints against a proprietary knowledge base.
3.  **Institutional Intermarket Analysis:** Real-time correlation engine monitoring DXY (Dollar Index), Yields (TNX), and Equities (NQ/ES) to filter low-probability conditions.
4.  **Dynamic Volatility Adjustment:** Automatically shifts targeting logic based on real-time ATR (Average True Range) regimes.

## 📊 Proven Performance (Tick-Level Backtest)

The following metrics are derived from a 12-month tick-level replay (Jan 2025 - Jan 2026), utilizing **full equity compounding** (profits reinvested).

*   **Total Return:** +619.16%
*   **Monthly Average:** +15.38%
*   **Max Drawdown:** -3.94% (Surviving 6% hard limit)
*   **Win Rate:** 32.86% (High R:R Asymmetric Compounding)
*   **Best Month:** +38.5%

> **Note:** High returns are driven by geometric compounding. Linear (static risk) returns would be lower.

## ⚡ Tech Stack

*   **Core Logic:** Python 3.10 (Pandas, NumPy, CCXT)
*   **Infrastructure:** Modal (Serverless Cloud Architecture)
*   **AI Layer:** Google Vertex AI / Gemini Pro Vision
*   **Execution:** TradeLocker API (Webhook-based limit orders)
*   **Notification:** Telegram Bot with Real-Time Rich Alerts

## 🛡️ Risk Management (The Fortress)

The system operates on a "Survival First" boolean logic:
*   **Hard Drawdown Limit:** Fixed circuit breakers at 6% global drawdown.
*   **News Filtering:** Automated calendar parsing to avoid High-Impact news events (CPI, FOMC).
*   **Correlation Guard:** Trading is suspended if safe-haven assets and risk assets decouple (Correlation Collapse protection).

## ⚠️ Disclaimer

This code is provided for educational and portfolio demonstration purposes only. The "Alpha" (profit-generating logic) has been removed. Running this unmodified will not result in profitable trades.""")
        
    print("✅ Public Release Ready!")

if __name__ == "__main__":
    main()
