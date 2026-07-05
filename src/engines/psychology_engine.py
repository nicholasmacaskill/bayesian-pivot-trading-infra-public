import os
import json
import logging
from datetime import datetime
from src.engines.ai_hub import SovereignAIHub
from src.core.config import Config

logger = logging.getLogger("PsychologyEngine")

class PsychologyEngine:
    def __init__(self, api_key=None):
        self.hub = SovereignAIHub()
            
        self.ledger_path = os.path.join(os.path.dirname(__file__), "psych_ledger.json")
        self.ledger = self._load_ledger()

    def _load_ledger(self):
        if os.path.exists(self.ledger_path):
            try:
                with open(self.ledger_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load psych ledger: {e}")
        return {"sessions": []}

    def _save_ledger(self):
        try:
            with open(self.ledger_path, 'w') as f:
                json.dump(self.ledger, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save psych ledger: {e}")

    def analyze_user_state(self, current_text=None, audio_path=None, physio_tilt=None):
        """
        Analyzes multimodal input to determine tilt level and sentiment.
        Optionally incorporates physio_tilt from BiometricEngine.
        """
        if not self.hub.has_ai:
            return {"tilt_score": 0, "sentiment": "Neutral", "reasoning": "AI Unavailable"}

        # Load Sovereign Prompts (Private IP)
        try:
            from src.sovereign_core.prompts.psychology_prompts import SOVEREIGN_PSYCHOLOGY_PROMPT
            sovereign_prompt = SOVEREIGN_PSYCHOLOGY_PROMPT
        except ImportError:
            sovereign_prompt = None

        if sovereign_prompt:
            prompt = sovereign_prompt.format(text=current_text or "No text provided")
        else:
            # Public Lite Version
            prompt = f"""
            Analyze the following trader text for emotional state.
            Trader text: "{current_text or 'No text provided'}"

            Return EXACTLY a JSON format like this, nothing else:
            {{
                "tilt_score": <1-10 score, where 1 is calm and 10 is highly tilted/emotional>,
                "sentiment": "<Calm, Frustrated, Anxious, Excited, or Neutral>",
                "reasoning": "<Reason for this classification>"
            }}
            """

        try:
            result = self.hub.analyze_setup(prompt)
            
            # Incorporate Physiological Tilt if provided
            if physio_tilt is not None:
                # If physio detects higher stress than AI, use physio
                result['tilt_score'] = max(result.get('tilt_score', 0), int(physio_tilt))
                result['physio_active'] = True
            
            # Update ledger
            session = {
                "timestamp": datetime.now().isoformat(),
                "tilt_score": result.get('tilt_score', 1),
                "sentiment": result.get('sentiment', 'Calm'),
                "text": current_text,
                "physio_tilt": physio_tilt
            }
            self.ledger['sessions'].append(session)
            if len(self.ledger['sessions']) > 50:
                self.ledger['sessions'].pop(0)
            self._save_ledger()
            
            return result
        except Exception as e:
            logger.error(f"Psychology analysis failed: {e}")
            if self.ledger.get('sessions'):
                last_session = self.ledger['sessions'][-1]
                return {
                    "tilt_score": last_session.get("tilt_score", 1),
                    "sentiment": last_session.get("sentiment", "Calm"),
                    "reasoning": f"AI API Error ({e}) - Fell back to last known state"
                }
            return {"tilt_score": 1, "sentiment": "Calm", "reasoning": str(e)}

    def get_risk_multiplier(self, tilt_score):
        """
        Returns a risk multiplier based on tilt level.
        Higher tilt = lower risk allowed (never cuts trading completely).
        """
        if tilt_score >= 8:
            return 0.25 # RISK FLOOR: Lower size instead of hard shutdown
        if tilt_score >= 6:
            return 0.5  # Half size
        if tilt_score >= 4:
            return 0.75 # 75% size
        return 1.0     # Normal

if __name__ == "__main__":
    # Quick test
    engine = PsychologyEngine()
    state = engine.analyze_user_state(current_text="I just lost three trades in a row and I need to make it back now. BTC is definitely going down.")
    print(json.dumps(state, indent=2))
