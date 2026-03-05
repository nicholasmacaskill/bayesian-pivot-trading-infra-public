import os
import json
import logging
from datetime import datetime, timezone
from google import genai
from src.core.config import Config

logger = logging.getLogger("PsychologyEngine")

class PsychologyEngine:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            
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

    def analyze_user_state(self, current_text=None, audio_path=None, physio_data=None):
        """
        Analyzes multimodal input to determine tilt level and sentiment.
        Optionally incorporates physio_data from BiometricEngine.
        """
        if not self.client:
            return {"tilt_score": 0, "sentiment": "Neutral", "reasoning": "AI Unavailable", "bpm_spike": False}

        physio_tilt = physio_data.get('score') if isinstance(physio_data, dict) else physio_data
        bpm_spike = physio_data.get('bpm_spike', False) if isinstance(physio_data, dict) else False

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
            prompt = f"Analyze the following trader text for emotional state (1-10 score): {current_text}"
        
        contents = [prompt]
        
        import time
        max_retries = 3
        base_delay = 2
        
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=contents,
                    config={'response_mime_type': 'application/json'}
                )
                result = json.loads(response.text)
                break  # Success
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"PsychologyEngine 429 Rate Limit. Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(delay)
                        continue
                logger.error(f"Psychology analysis failed after {attempt+1} attempts: {e}")
                return {"tilt_score": 0, "sentiment": "Error", "reasoning": str(e), "bpm_spike": bpm_spike}
        else:
            return {"tilt_score": 0, "sentiment": "Error", "reasoning": "Max retries exceeded", "bpm_spike": bpm_spike}
            
        try:
            if physio_tilt is not None:
                # If physio detects higher stress than AI, use physio
                result['tilt_score'] = max(result.get('tilt_score', 0), int(physio_tilt))
                result['physio_active'] = True
            
            result['bpm_spike'] = bpm_spike
            
            # Update ledger
            session = {
                "timestamp": datetime.now().isoformat(),
                "tilt_score": result['tilt_score'],
                "sentiment": result['sentiment'],
                "text": current_text,
                "physio_tilt": physio_tilt,
                "bpm_spike": bpm_spike
            }
            self.ledger['sessions'].append(session)
            if len(self.ledger['sessions']) > 50:
                self.ledger['sessions'].pop(0)
            self._save_ledger()
            
            return result
        except Exception as e:
            logger.error(f"Psychology analysis failed: {e}")
            return {"tilt_score": 0, "sentiment": "Error", "reasoning": str(e), "bpm_spike": bpm_spike}

    def get_risk_multiplier(self, tilt_score, bpm_spike=False):
        """
        Returns a risk multiplier based on tilt level.
        Higher tilt = lower risk allowed (or forced shutdown).
        BPM Spike alone does NOT reduce risk.
        """
        if tilt_score >= 8:
            return 0.0  # HARD SHUTDOWN
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
