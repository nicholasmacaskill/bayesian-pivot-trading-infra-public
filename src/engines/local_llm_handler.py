import requests
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

SETUP_SCORING_PROMPT = """You are a professional ICT (Inner Circle Trader) algorithmic trading analyst.
Analyze this trade setup and return a JSON object with exactly these fields:
{
  "score": <float 0-10, precision 1 decimal>,
  "verdict": "<EXECUTE|WATCH|SKIP>",
  "reasoning": "<max 2 sentences, why this setup does or doesn't qualify>",
  "risk_level": "<LOW|MEDIUM|HIGH>"
}

Scoring rubric:
- 8.5-10: Unicorn setup — all confluence aligned, killzone confirmed, HTF POI as draw on liquidity
- 7.0-8.4: High alpha — strong pattern, clean bias, session timing confirmed
- 5.0-6.9: Watchlist — some confluence, but missing key confirmation
- 0-4.9: Skip — weak or conflicting signals

Setup to analyze:
SYMBOL: {symbol}
PATTERN: {pattern}
DIRECTION: {direction}
HTF BIAS: {bias}
HURST EXPONENT: {hurst} ({hurst_regime})
SESSION: {session}
ENTRY: {entry}
STOP LOSS: {stop_loss}
INTERMARKET: DXY={dxy_trend}, NQ={nq_trend}
ATR%ILE: {atr_percentile}

Return ONLY the JSON object. No markdown, no explanation, just the raw JSON."""


class LocalLLMHandler:
    """
    Offline AI redundancy using a local LLM via Ollama.
    Ensures analysis uptime even if all cloud APIs are unreachable.
    Provides full structured scoring at zero API cost.
    """
    def __init__(self, model: str = "llama3", url: str = "http://localhost:11434/api/generate"):
        self.model = model
        self.url = url
        self._timeout = 30

    def is_available(self) -> bool:
        """Checks if the local Ollama server is running."""
        try:
            response = requests.get(
                self.url.replace("/api/generate", "/api/tags"),
                timeout=2
            )
            return response.status_code == 200
        except:
            return False

    def score_setup(self, setup: Dict[str, Any], market_context: Optional[Dict] = None,
                    hurst: float = 0.5, session_info: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Score a trade setup using the local Llama3 model.
        Returns the same schema as cloud validators: {score, verdict, reasoning, risk_level}.
        """
        hurst_regime = "Mean-Reverting (Turtle Soup)" if hurst < 0.45 else (
            "Trending (Displacement)" if hurst > 0.55 else "Neutral"
        )
        dxy_trend = "N/A"
        nq_trend = "N/A"
        if market_context:
            dxy_trend = market_context.get("DXY", {}).get("trend", "N/A")
            nq_trend = market_context.get("NQ", {}).get("trend", "N/A")

        session = session_info.get("name", "Unknown") if session_info else "Unknown"
        atr_pct = setup.get("atr_percentile", "N/A")

        prompt = SETUP_SCORING_PROMPT.format(
            symbol=setup.get("symbol", "N/A"),
            pattern=setup.get("pattern", "N/A"),
            direction=setup.get("direction", setup.get("bias", "N/A")),
            bias=setup.get("bias", "N/A"),
            hurst=f"{hurst:.3f}",
            hurst_regime=hurst_regime,
            session=session,
            entry=setup.get("entry", "N/A"),
            stop_loss=setup.get("stop_loss", "N/A"),
            dxy_trend=dxy_trend,
            nq_trend=nq_trend,
            atr_percentile=atr_pct,
        )

        raw = self.analyze(prompt)
        result = self._parse_score(raw)
        result["provider"] = "Llama3-Local"
        return result

    def analyze(self, prompt: str, image_path: Optional[str] = None) -> str:
        """
        Perform text analysis using the local model. Returns raw response string.
        Note: Llama3 8B is text-only — image_path is accepted but ignored.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,   # Low temp for structured/consistent scoring
                "num_predict": 256,   # Cap tokens to keep RAM/latency tight
            }
        }
        try:
            response = requests.post(self.url, json=payload, timeout=self._timeout)
            response.raise_for_status()
            raw = response.json().get('response', '{}')
            logger.info(f"🦙 Llama3 response received ({len(raw)} chars)")
            return raw
        except Exception as e:
            logger.error(f"Local LLM Error: {e}")
            raise e

    def _parse_score(self, raw: str) -> Dict[str, Any]:
        """Parse and validate the scoring response, with safe fallback."""
        import re
        try:
            # Strip any surrounding markdown/noise
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                score = float(data.get("score", 0))
                score = max(0.0, min(10.0, score))  # Clamp to valid range
                return {
                    "score": score,
                    "verdict": data.get("verdict", "SKIP"),
                    "reasoning": data.get("reasoning", "Local LLM analysis."),
                    "risk_level": data.get("risk_level", "MEDIUM"),
                }
        except Exception as e:
            logger.warning(f"Llama3 parse error: {e} | Raw: {raw[:100]}")
        # Safe fallback — never crash the pipeline
        return {"score": 0.0, "verdict": "SKIP", "reasoning": "Local LLM parse error.", "risk_level": "HIGH"}
