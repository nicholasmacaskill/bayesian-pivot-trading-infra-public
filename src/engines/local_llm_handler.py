import requests
import json
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LocalLLMHandler:
    """
    Offline AI redundancy using a local SLM (e.g., Ollama).
    Ensures analysis uptime even if all cloud APIs are unreachable.
    """
    def __init__(self, model: str = "llama3", url: str = "http://localhost:11434/api/generate"):
        self.model = model
        self.url = url

    def is_available(self) -> bool:
        """Checks if the local Ollama server is running."""
        try:
            response = requests.get(self.url.replace("/api/generate", "/api/tags"), timeout=2)
            return response.status_code == 200
        except:
            return False

    def analyze(self, prompt: str, image_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Perform analysis using the local model.
        Note: Image support depends on the model (e.g., llava or llama3-vision).
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json"
        }
        
        # Basic text-only for now, can be extended for vision models
        try:
            response = requests.post(self.url, json=payload, timeout=30)
            response.raise_for_status()
            return response.json().get('response', '{}')
        except Exception as e:
            logger.error(f"Local LLM Error: {e}")
            raise e
