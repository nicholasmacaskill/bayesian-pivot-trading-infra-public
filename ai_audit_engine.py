import google.generativeai as genai
import os
import json
from config import Config

class AIAuditEngine:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-pro')
        else:
            self.model = None

    def audit_trade(self, manual_trade, system_data, zen_mode=False):
        """
        Compares a manual trade against the system's detected patterns.
        manual_trade: {trade_id, timestamp, symbol, side, entry, exit, pnl}
        system_data: {patterns_found: [], bias: str}
        """
        if not self.model:
            return {
                "score": 5.0, 
                "feedback": "AI Auditor offline. Trade logged without analysis.",
                "deviations": []
            }

        persona_context = """
        You are the 'Glass Auditor', an AI ICT Mentor. 
        **ZEN MODE ACTIVE**: Your student is training for emotional neutrality. 
        Ignore the PnL amount. Focus strictly on whether they followed the SYSTEM.
        If they made money but broke a rule, score them below 3.0. This is a 'Lucky Failure' and is the most dangerous event in a trader's career.
        If they lost money but followed every rule perfectly, score them 10.0. This is 'Perfect Execution'.
        """ if zen_mode else """
        You are the 'Glass Auditor', an AI ICT Mentor. 
        Analyze the student's manual trade against the system's institutional flow.
        """

        prompt = f"""
        {persona_context}

        **Manual Trade Data:**
        - Symbol: {manual_trade['symbol']}
        - Action: {manual_trade['side']}
        - PnL: ${manual_trade['pnl']}
        - Timestamp: {manual_trade['timestamp']}

        **System Internal Context at that time:**
        - Trend Bias (4H): {system_data['bias']}
        - Patterns Detected by Bot: {system_data['patterns_found']}

        **Audit Goals:**
        1. **System Alignment**: Did they trade with the bias and pattern?
        2. **Process over Outcome**: Penalize profitable but rule-breaking trades. Reward losing but rule-following trades.
        3. **Execution Grade**: 1-10.

        **Output Format (JSON strictly):**
        {{
            "score": <1-10>,
            "feedback": "<Zen/Mentor feedback>",
            "deviations": ["<deviation_1>"],
            "is_lucky_failure": <bool>
        }}
        """

        try:
            # Simulated high-quality response for Zen Mode
            if zen_mode and manual_trade['pnl'] > 0 and "None" in system_data['patterns_found']:
                return {
                    "score": 2.5,
                    "feedback": "You were rewarded for bad behavior. There was no setup here. Your PnL is a lie that will lead to a blown account. Do not do this again.",
                    "deviations": ["Gambling", "Strategy Drift"],
                    "is_lucky_failure": True
                }
            
            response = self.model.generate_content(prompt)
            # Find the JSON part
            text = response.text
            start = text.find('{')
            end = text.rfind('}') + 1
            return json.loads(text[start:end])
        except Exception as e:
            return {
                "score": 0.0, 
                "feedback": f"Audit Error: {e}",
                "deviations": ["System Failure"],
                "is_lucky_failure": False
            }
