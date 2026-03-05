import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.vitals import verify_vitals
from src.clients.telegram_notifier import TelegramNotifier

def run_report():
    """
    LOCAL YARD MONITORING:
    Performs vitals check and sends a formatted Telegram report.
    Designed for local cron execution.
    """
    # Load local env (priority)
    load_dotenv(".env.local")
    load_dotenv(".env")
    
    print("🛡️ Starting Local Yard Vitals Check...")
    report = verify_vitals()
    
    notifier = TelegramNotifier()
    now = datetime.now()
    
    emoji = "✅" if report["status"] == "HEALTHY" else "⚠️"
    
    msg = (
        f"{emoji} *YARD MODE: DAILY HEALTH REPORT*\n"
        f"📅 Date: `{now.strftime('%Y-%m-%d %H:%M:%S')}`\n"
        f"📈 Status: *{report['status']}*\n\n"
        f"*Current Vitals:*\n"
    )
    
    for check, status in report["checks"].items():
        msg += f"• {check}: {status}\n"
        
    if report["issues"]:
        msg += f"\n🚨 *Detected Issues:*\n"
        for issue in report["issues"]:
            msg += f"- {issue}\n"
            
    msg += (
        f"\n🚀 *Execution Profile:* `Bayesian Pivot (Local)`\n"
        f"🎯 *Expected ROI:* `+139.3% / year`"
    )

    notifier._send_message(msg)
    print(f"✅ Local Health Report Sent. Status: {report['status']}")

if __name__ == "__main__":
    run_report()
