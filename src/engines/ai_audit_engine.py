from google import genai
import os
import json
from src.core.config import Config

class AIAuditEngine:
    def __init__(self, api_key=None):
        # Try explicit -> Config -> Env
        self.api_key = api_key or getattr(Config, 'GEMINI_API_KEY', None) or os.environ.get("GEMINI_API_KEY")
        
        if not self.api_key:
             from dotenv import load_dotenv
             load_dotenv(".env.local")
             self.api_key = os.environ.get("GEMINI_API_KEY")

        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def get_text_embedding(self, text):
        """Generates a 768-dimensional vector for the given text."""
        if not self.client: 
            return []
        try:
            result = self.client.models.embed_content(
                model="text-embedding-004",
                contents=text,
                config={
                    "task_type": "RETRIEVAL_DOCUMENT",
                    "title": "Trade Logic",
                    "output_dimensionality": 768
                }
            )
            emb = result.embeddings[0].values
            return emb
        except Exception as e:
            print(f"DEBUG EMBED ERROR: {e}")
            return []

    def audit_trade(self, manual_trade, system_data, zen_mode=False):
        """
        Compares a manual trade against the system's detected patterns.
        manual_trade: {trade_id, timestamp, symbol, side, entry, exit, pnl}
        system_data: {patterns_found: [], bias: str}
        """
        if not self.client:
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
            
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            return json.loads(response.text)
        except Exception as e:
            return {
                "score": 0.0, 
                "feedback": f"Audit Error: {e}",
                "deviations": ["System Failure"],
                "is_lucky_failure": False
            }
    def audit_discretionary_trade(self, manual_trade):
        """
        Analyzes a trade taken WITHOUT a system signal.
        Goal: Identify 'Alpha' (Human intuition/missed setup) vs 'Rogue' (Gambling).
        """
        if not self.client:
            return {"score": 5.0, "feedback": "Auditor offline.", "is_alpha": False}

        prompt = f"""
        You are the 'Glass Auditor', analyzing a DISCRETIONARY trade.
        The bot scanner did NOT flag this setup, but the human took it anyway.

        **Manual Trade:**
        - Symbol: {manual_trade['symbol']}
        - Action: {manual_trade['side']}
        - PnL: ${manual_trade['pnl']}
        - Entry/Exit Context: {manual_trade.get('notes', 'No notes provided')}

        **Your Mission:**
        1. **Alpha Hunt**: Was there a valid SMC/ICT setup here (Liquidity grab, MSS, Inducement) that the scanner might have missed?
        2. **Grade it (1-10)**: 
           - 8-10: 'Human Alpha' (Good eyes, the model should learn this).
           - 4-7: 'Average Discretion' (Context was okay, but risky).
           - 1-3: 'Rogue/Gambling' (No clear logic).
        3. **Model Feedback**: How could we improve the bot scanner to detect this in the future?

        **Output Format (JSON strictly):**
        {{
            "score": <score>,
            "feedback": "<Expert analysis>",
            "is_alpha": <bool>,
            "improvement_suggestion": "<how to fix the bot>"
        }}
        """

        try:
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt,
                config={'response_mime_type': 'application/json'}
            )
            return json.loads(response.text)
        except Exception as e:
            return {"score": 3.0, "feedback": f"Discordant Audit Error: {e}", "is_alpha": False}

