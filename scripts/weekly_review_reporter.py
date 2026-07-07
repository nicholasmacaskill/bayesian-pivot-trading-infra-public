import os
import logging
from datetime import datetime, timedelta
from src.core.supabase_client import supabase
from ai_audit_engine import AIAuditEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StrategyReview")

class StrategyReviewReporter:
    def __init__(self):
        self.sb = supabase
        self.ai = AIAuditEngine()

    def generate_report(self, days=7):
        """
        Gathers data from the Vector DB and generates a Strategy Council Report.
        """
        logger.info(f"📊 Generating Weekly Strategy Review (Last {days} days)...")
        
        # 1. Fetch Journal Entries
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        try:
            resp = self.sb.client.table("journal")\
                .select("*")\
                .gt("timestamp", cutoff)\
                .execute()
            
            entries = resp.data
            if not entries:
                return "No trade activity found in the last week. Keep sniping!"
            
            # 2. Categorize for the AI
            winning_alphas = [e for e in entries if e.get('strategy') == 'ALPHA' and e.get('pnl', 0) > 0]
            system_losses = [e for e in entries if e.get('strategy') == 'SYSTEM' and e.get('pnl', 0) < 0]
            rogue_trades = [e for e in entries if e.get('strategy') == 'ROGUE']
            
            # 3. Use AI to synthesize vectors (Conceptual grouping)
            # We pass the feedback/grades to Gemini to find the 'theme'
            report_data = {
                "total_trades": len(entries),
                "win_rate": len([e for e in entries if e.get('pnl', 0) > 0]) / len(entries),
                "alphas": winning_alphas,
                "losses": system_losses,
                "rogues": rogue_trades
            }
            
            prompt = f"""
            You are the 'Glass Auditor', acting as the Lead Strategy Architect.
            Analyze the following weekly trading data (Feedback & Grades).
            
            **Weekly Stats:**
            - Total Trades: {report_data['total_trades']}
            - Win Rate: {report_data['win_rate']:.2%}
            
            **Winning ALPHA Plays (Discretionary success the bot missed):**
            {self._format_entries(winning_alphas)}
            
            **System Failures (Bot followed rules but lost):**
            {self._format_entries(system_losses)}
            
            **Rogue Behavior:**
            {len(rogue_trades)} trades were taken without any signal.
            
            **Goal**: 
            1. Identify 2 specific ways to IMPROVE the bot's Python scanner based on the ALPHA plays.
            2. Identify if there is a 'Regime Shift' (e.g., FVGs are failing more often).
            3. Provide a 'Strategy Council Decision' for the next week.
            
            Format as a beautiful Markdown Report.
            """
            
            response = self.ai.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            logger.error(f"Report Generation Failed: {e}")
            return f"Error generating report: {e}"

    def _format_entries(self, entries):
        if not entries: return "None"
        formatted = []
        for e in entries:
            formatted.append(f"- {e['symbol']} {e['side']}: Grade {e['ai_grade']} | Feedback: {e['mentor_feedback']}")
        return "\n".join(formatted)

if __name__ == "__main__":
    reporter = StrategyReviewReporter()
    report = reporter.generate_report(days=7)
    print("\n" + "="*50)
    print("      WEEKLY STRATEGY COUNCIL REPORT")
    print("="*50 + "\n")
    print(report)
    
    # Save to file
    with open("weekly_strategy_report.md", "w") as f:
        f.write(report)
    print(f"\n✅ Report saved to weekly_strategy_report.md")
