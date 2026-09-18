import requests
import json
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are Bayesian Pivot, an elite institutional quantitative trading AI validator specialized in Inner Circle Trader (ICT) and Smart Money Concepts (SMC) order flow mechanics.
Analyze this candidate trade setup and return a structured JSON evaluation with exactly these fields:
{
  "score": <float 0.0-10.0 continuous probability>,
  "verdict": "<FLOW_GO|SHADOW_OBSERVATION|REJECTED>",
  "reasoning": "<1-2 sentences on specific institutional confluence or trap veto>",
  "risk_multiplier": <float 0.0 to 1.33>,
  "risk_level": "<LOW|MEDIUM|HIGH>"
}
Scoring Rubric:
- 8.5-10.0: Tier 1 Unicorn (Sweep of HTF POI + strong SMT divergence + verified CVD limit absorption)
- 7.5-8.4: A-Tier Production Alpha (Clean killzone timing + HTF trend alignment)
- 5.0-7.4: Sub-Threshold (Quarantined to $0 risk shadow observation)
- 0.0-4.9: Toxic Retail Trap / Invalidation (Veto / Reject immediately)"""


class LocalLLMHandler:
    """
    Offline & Redundant Local AI Engine for Bayesian Pivot.
    Primary: Local MLX server running fine-tuned LoRA on Apple Silicon GPU (port 8080).
    Secondary: Local Ollama server (port 11434).
    Provides structured 5-Pillar orderflow validation at $0 API cost and zero live risk.
    """
    def __init__(
        self,
        model: str = "mlx-community/Qwen2.5-Coder-1.5B-Instruct-4bit",
        mlx_url: str = "http://127.0.0.1:8080/v1",
        ollama_url: str = "http://localhost:11434/api",
        timeout: int = 15
    ):
        self.model = model
        self.mlx_url = mlx_url.rstrip("/")
        self.ollama_url = ollama_url.rstrip("/")
        self._timeout = timeout
        self.active_backend: Optional[str] = None
        self.active_provider: str = "Local-LLM"

    def is_available(self) -> bool:
        """
        Checks local AI availability:
        1. Checks MLX local server on port 8080 (Primary M4 LoRA).
        2. Falls back to Ollama on port 11434.
        """
        # Priority 1: MLX Local Server (Apple Silicon LoRA)
        try:
            resp = requests.get(f"{self.mlx_url}/models", timeout=1.5)
            if resp.status_code == 200:
                self.active_backend = "mlx"
                self.active_provider = "MLX-LoRA-Local-M4"
                return True
        except Exception:
            pass

        # Priority 2: Ollama Local Server
        try:
            resp = requests.get(f"{self.ollama_url}/tags", timeout=1.5)
            if resp.status_code == 200:
                self.active_backend = "ollama"
                self.active_provider = "Ollama-Local"
                return True
        except Exception:
            pass

        self.active_backend = None
        return False

    def build_5pillar_prompt(
        self,
        setup: Dict[str, Any],
        market_context: Optional[Dict] = None,
        hurst: float = 0.5,
        session_info: Optional[Dict] = None
    ) -> str:
        """
        Constructs the institutional 5-Pillar prompt matching the training distribution:
        SESSION, PD ARRAY, VOLUME, SMT CONFLUENCE, HTF STRUCTURE, ORDERFLOW.
        """
        # 1. Archetype & Direction
        raw_pattern = str(setup.get("pattern", "")).upper()
        direction = str(setup.get("direction", setup.get("bias", "LONG"))).upper()
        symbol = str(setup.get("symbol", "BTC/USD"))

        if "TURTLE" in raw_pattern or "SWEEP" in raw_pattern or "JUDAS" in raw_pattern:
            archetype = "TURTLE_SOUP_FADER"
        elif "EXPANSION" in raw_pattern or "TREND" in raw_pattern:
            archetype = "TREND_EXPANSION"
        else:
            archetype = "CORE_ANCHOR"

        # 2. Session Context
        session_name = (session_info.get("name") if session_info else setup.get("session", "UNKNOWN")).upper()
        if "NY" in session_name or "NEW YORK" in session_name:
            session_desc = "New York AM Session (Institutional Expansion)"
        elif "LONDON" in session_name:
            session_desc = "London Open Killzone (Institutional Drive)"
        elif "ASIA" in session_name:
            session_desc = "Asian Session (Retail Liquidity Accumulation)"
        elif "MACRO" in session_name or "SILVER" in session_name:
            session_desc = "Institutional Macro Window (High Liquidity)"
        else:
            session_desc = f"{session_name} Session"

        # 3. PD Array Dealing Range
        pd_array = setup.get("pd_array")
        if not pd_array:
            discount_pct = setup.get("discount_pct", None)
            if discount_pct is not None:
                if direction == "LONG" and discount_pct >= 0.5:
                    pd_array = f"Discount Dealing Range ({discount_pct*100:.0f}% Discount POI)"
                elif direction == "SHORT" and discount_pct <= 0.5:
                    pd_array = f"Premium Dealing Range ({(1-discount_pct)*100:.0f}% Premium POI)"
                else:
                    pd_array = "Equilibrium Dealing Range"
            else:
                if direction == "LONG":
                    pd_array = "Discount Dealing Range (HTF Bullish FVG / Order Block)"
                else:
                    pd_array = "Premium Dealing Range (HTF Bearish FVG / Order Block)"

        # 4. Volume Expansion
        vol_mult = setup.get("relative_volume", setup.get("vol_mult", 1.0))
        if vol_mult >= 1.5:
            volume_desc = f"{vol_mult:.1f}x Relative Volume Expansion"
        elif vol_mult <= 0.5:
            volume_desc = f"{vol_mult:.1f}x Relative Volume Trickle (Weak Retail)"
        else:
            volume_desc = f"{vol_mult:.1f}x Relative Volume (Neutral)"

        # 5. SMT Confluence
        smt_desc = setup.get("smt_confluence")
        if not smt_desc:
            smt_strength = setup.get("smt_strength", 0.0)
            if smt_strength > 0.4:
                smt_desc = f"Confirmed Intermarket SMT Divergence (Strength: {smt_strength:.2f})"
            elif market_context and market_context.get("DXY", {}).get("trend"):
                dxy_trend = market_context.get("DXY", {}).get("trend")
                smt_desc = f"Macro Dollar Bias: DXY {dxy_trend}"
            else:
                smt_desc = "N/A"

        # 6. HTF Structure
        htf_desc = setup.get("htf_structure")
        if not htf_desc:
            trend = setup.get("trend", setup.get("bias", "NEUTRAL"))
            hurst_text = f"Hurst {hurst:.2f}"
            htf_desc = f"{trend} Trend Alignment ({hurst_text})"

        # 7. Orderflow Dynamics
        orderflow_desc = setup.get("orderflow")
        if not orderflow_desc:
            cvd_abs = setup.get("cvd_absorption", False)
            if cvd_abs:
                orderflow_desc = "Verified CVD limit absorption at liquidity pool"
            else:
                orderflow_desc = "Orderflow displacement confirming institutional participation"

        prompt = (
            f"EVALUATE INSTITUTIONAL SETUP:\n"
            f"ARCHETYPE: [{archetype}] | PROVENANCE: [ERA_4_SHADOW_LAB]\n"
            f"SYMBOL: {symbol} | DIRECTION: {direction}\n"
            f"SESSION: {session_desc}\n"
            f"PD ARRAY: {pd_array}\n"
            f"VOLUME: {volume_desc}\n"
            f"SMT CONFLUENCE: {smt_desc}\n"
            f"HTF STRUCTURE: {htf_desc}\n"
            f"ORDERFLOW: {orderflow_desc}"
        )
        return prompt

    def score_setup(
        self,
        setup: Dict[str, Any],
        market_context: Optional[Dict] = None,
        hurst: float = 0.5,
        session_info: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Scores candidate trade setup using local Apple Silicon MLX LoRA or Ollama.
        Returns unified schema: {score, verdict, reasoning, risk_multiplier, risk_level, provider}.
        """
        if not self.is_available():
            return {
                "score": 0.0,
                "verdict": "REJECTED",
                "reasoning": "Local LLM server is offline.",
                "risk_multiplier": 0.0,
                "risk_level": "HIGH",
                "provider": "Offline"
            }

        prompt = self.build_5pillar_prompt(
            setup=setup,
            market_context=market_context,
            hurst=hurst,
            session_info=session_info
        )

        try:
            if self.active_backend == "mlx":
                # MLX HTTP Chat Completions (OpenAI Compatible)
                payload = {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT + "\nKeep reasoning under 30 words so the JSON object closes cleanly."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 350
                }
                resp = requests.post(
                    f"{self.mlx_url}/chat/completions",
                    json=payload,
                    timeout=self._timeout
                )
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["choices"][0]["message"]["content"]
                result = self._parse_score(raw_text)
                result["provider"] = "MLX-LoRA-Local-M4"
                result["backend"] = "mlx"
                return result

            elif self.active_backend == "ollama":
                # Ollama Generate endpoint
                payload = {
                    "model": "bayesian-pivot",
                    "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 300}
                }
                resp = requests.post(
                    f"{self.ollama_url}/generate",
                    json=payload,
                    timeout=self._timeout
                )
                resp.raise_for_status()
                raw_text = resp.json().get("response", "{}")
                result = self._parse_score(raw_text)
                result["provider"] = "Ollama-Local"
                result["backend"] = "ollama"
                return result

        except Exception as e:
            logger.warning(f"Local LLM inference error: {e}")

        # Safe fallback — never crash production
        return {
            "score": 0.0,
            "verdict": "REJECTED",
            "reasoning": "Local LLM inference fallback triggered.",
            "risk_multiplier": 0.0,
            "risk_level": "HIGH",
            "provider": self.active_provider
        }

    def analyze(self, prompt: str, image_path: Optional[str] = None) -> str:
        """
        Generic text inference method for ai_hub fallback compatibility.
        """
        if not self.is_available():
            raise RuntimeError("Local LLM server is not available.")

        try:
            if self.active_backend == "mlx":
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 350
                }
                resp = requests.post(
                    f"{self.mlx_url}/chat/completions",
                    json=payload,
                    timeout=self._timeout
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            else:
                payload = {
                    "model": "bayesian-pivot",
                    "prompt": prompt,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1, "num_predict": 300}
                }
                resp = requests.post(
                    f"{self.ollama_url}/generate",
                    json=payload,
                    timeout=self._timeout
                )
                resp.raise_for_status()
                return resp.json().get("response", "{}")
        except Exception as e:
            logger.error(f"Local LLM analyze error: {e}")
            raise e

    def _parse_score(self, raw: str) -> Dict[str, Any]:
        """Parse structured JSON scoring response with multi-pattern fallback."""
        clean = raw.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        # Strategy 1: Direct or Regex JSON load
        match = re.search(r"\{.*\}", clean, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                score = float(data.get("score", 0.0))
                score = max(0.0, min(10.0, score))
                verdict = str(data.get("verdict", "SHADOW_OBSERVATION")).upper()
                if verdict not in ["FLOW_GO", "SHADOW_OBSERVATION", "REJECTED"]:
                    verdict = "SHADOW_OBSERVATION"
                reasoning = str(data.get("reasoning", "Local AI evaluation."))
                risk_mult = float(data.get("risk_multiplier", 1.0 if verdict == "FLOW_GO" else 0.0))
                risk_mult = max(0.0, min(1.33, risk_mult))
                risk_lvl = str(data.get("risk_level", "MEDIUM")).upper()

                return {
                    "score": round(score, 2),
                    "verdict": verdict,
                    "reasoning": reasoning,
                    "risk_multiplier": round(risk_mult, 2),
                    "risk_level": risk_lvl
                }
            except Exception:
                pass

        # Strategy 2: Resilient field extraction if JSON closing brace was truncated
        try:
            score_m = re.search(r'"score"\s*:\s*([0-9.]+)', clean)
            verdict_m = re.search(r'"verdict"\s*:\s*"([^"]+)"', clean)
            reasoning_m = re.search(r'"reasoning"\s*:\s*"([^"]+)"', clean)
            risk_m = re.search(r'"risk_multiplier"\s*:\s*([0-9.]+)', clean)
            level_m = re.search(r'"risk_level"\s*:\s*"([^"]+)"', clean)

            if score_m or verdict_m:
                score = float(score_m.group(1)) if score_m else 5.0
                score = max(0.0, min(10.0, score))
                verdict = verdict_m.group(1).upper() if verdict_m else ("FLOW_GO" if score >= 7.5 else "REJECTED")
                reasoning = reasoning_m.group(1) if reasoning_m else clean[:120].replace("\n", " ")
                risk_mult = float(risk_m.group(1)) if risk_m else (1.0 if verdict == "FLOW_GO" else 0.0)
                risk_mult = max(0.0, min(1.33, risk_mult))
                risk_lvl = level_m.group(1).upper() if level_m else "MEDIUM"

                return {
                    "score": round(score, 2),
                    "verdict": verdict,
                    "reasoning": reasoning,
                    "risk_multiplier": round(risk_mult, 2),
                    "risk_level": risk_lvl
                }
        except Exception as e:
            logger.warning(f"Resilient parse error: {e}")

        return {
            "score": 0.0,
            "verdict": "REJECTED",
            "reasoning": "Output parsing fallback.",
            "risk_multiplier": 0.0,
            "risk_level": "HIGH"
        }
