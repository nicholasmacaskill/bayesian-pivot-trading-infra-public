# [PUBLIC PORTFOLIO VERSION]
# NOTE: Core proprietary logic and parameters have been redacted/standardized.
# This repository demonstrates architecture, not live trading alpha.

import os
import json
from google import genai
from config import Config

class AIValidator:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            
        # Load ICT Oracle Knowledge Base
        self.kb_path = None # [PROPRIETARY KNOWLEDGE BASE - LICENSE REQUIRED]
        self.oracle_kb = {}
        if os.path.exists(self.kb_path):
            try:
                with open(self.kb_path, 'r') as f:
                    self.oracle_kb = json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load Oracle KB: {e}")

    def _get_oracle_prompt(self, pattern):
        """Extracts relevant ground truth from the Oracle KB."""
        if not self.oracle_kb:
            return ""
        
        concepts = self.oracle_kb.get('core_concepts', {})
        ground_truth = "### 🔮 THE ORACLE GROUND TRUTH (MICHAEL'S TEACHINGS):\n"
        
        # Match pattern to KB concept
        matched = False
        for key, details in concepts.items():
            if key.lower().replace("_", " ") in pattern.lower():
                ground_truth += f"- {details['full_name'] if 'full_name' in details else key}: {details['logic'] if 'logic' in details else details['definition']}\n"
                if 'validation' in details:
                    ground_truth += f"  - Validation Rule: {details['validation']}\n"
                matched = True
        
        # Default fallback to core if no specific pattern matched
        if not matched:
            po3 = concepts.get('PO3', {})
            ground_truth += f"- PO3 Baseline: {po3.get('logic', 'Accumulation, Manipulation, Distribution.')}\n"
            
        return ground_truth

    def hard_logic_audit(self, setup):
        """
        Air-Gapped Fallback: Mathematical validation when AI is unavailable.
        """
        score = 0
        reasoning_parts = []
        
        smt = setup.get('smt_strength', 0)
        if smt >= 0.5:
            score += 3
            reasoning_parts.append(f"Strong SMT ({smt})")
        
        cross_asset = setup.get('cross_asset_divergence', 0)
        if abs(cross_asset) >= 0.5:
            score += 3
            reasoning_parts.append(f"Cross-Asset Aligned ({cross_asset})")
        
        if setup.get('time_quartile', {}).get('num') == 2:
            score += 2
            reasoning_parts.append("Q2 Judas Window")
        
        if setup.get('is_discount') or setup.get('is_premium'):
            score += 2
            reasoning_parts.append("Valid Quartile")
        
        return {
            "score": float(score),
            "verdict": "HARD_LOGIC_PASS" if score >= 7 else "HARD_LOGIC_REJECT",
            "reasoning": f"FALLBACK MODE: {' | '.join(reasoning_parts)}. Score: {score}/10",
            "execution_logic": "Standard 1:3 RR with tight SL at invalidation point",
            "discipline_check": "Air-gapped audit - AI unavailable"
        }

    def analyze_trade(self, setup, sentiment, whales, image_path=None):
        """
        Calls Gemini API to validate the setup. Supports Vision and Oracle Grounding.
        """
        if not self.client:
            return {
                "score": 5.0, 
                "reasoning": "AI inactive (Missing Key). Proceed with manual caution.",
                "guidance": "Check Killzone and PD Arrays manually."
            }

        # Dynamic Oracle Grounding
        oracle_rules = self._get_oracle_prompt(setup.get('pattern', 'PO3'))

        prompt = f"""
        [SYSTEM PROMPT REDACTED FOR IP PROTECTION - PROPRIETARY ORACLE LOGIC]"""

        if image_path:
            prompt += """
        ### VISUAL MANDATE (VISION ACTIVE):
        The attached chart shows the setup. 
        1. Inspect the displacement wicks. Is there true institutional sponsorship (long bodies)?
        2. Identify the nearest FVG. Does price respect it or slice through it?
        3. Cross-reference the visual with the Oracle Ground Truth logic.
        """

        prompt += """
        ### YOUR VERDICT:
        Return surgical analysis in JSON. You MUST cite the specific Oracle Ground Truth used.
        {{
            "score": <0.0-10.0>,
            "verdict": "<FLOW_GO | REJECTED | INDUCEMENT_WARNING>",
            "reasoning": "<Analyze confluence and cite Oracle rules>",
            "execution_logic": "<SL/TP adjustments>",
            "discipline_check": "<Drawdown/Lucky failure warnings>"
        }}
        """

        try:
            # For development, we return a simulated result if the key is 'MOCK'
            if self.api_key == "MOCK":
                return {
                    "score": 8.5,
                    "verdict": "FLOW_GO",
                    "reasoning": f"MOCK: Grounded in {setup.get('pattern')}. Chart shows institutional sponsorship as per Oracle rules.",
                    "execution_logic": "Execute at FVG",
                    "discipline_check": "Good discipline"
                }

            contents = [prompt]
            if image_path and os.path.exists(image_path):
                from PIL import Image
                img = Image.open(image_path)
                contents.append(img)

            response = self.client.models.generate_content(
                model='gemini-2.0-flash', 
                contents=contents
            )
            
            text = response.text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start != -1 and end != -1:
                return json.loads(text[start:end])
            else:
                return {"score": 0.0, "reasoning": "AI Output Parsing Error", "guidance": "Manual review required"}
                
        except Exception as e:
            print(f"⚠️ AI Timeout/Error: {e}. Switching to HARD LOGIC FALLBACK.")
            return self.hard_logic_audit(setup)

def validate_setup(setup, sentiment, whales, image_path=None):
    validator = AIValidator()
    return validator.analyze_trade(setup, sentiment, whales, image_path=image_path)
