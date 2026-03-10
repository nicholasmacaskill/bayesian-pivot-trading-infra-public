"""
AI Validator — Sovereign Edge Engine
======================================
Evaluates raw SMC signals using a local LLM (Ollama / Llama3) and assigns
a conviction score from 0–10. Only signals above the configured threshold
are forwarded to the execution pipeline.

Capabilities (implementation is private):
  - Multi-factor prompt construction from signal context
  - Structured JSON score extraction from LLM output
  - Fallback scoring when model is unavailable
  - Async-safe design for concurrent symbol scanning

Usage::

    validator = AIValidator()
    result = validator.validate(signal)
    # result = {"score": 8.2, "reasoning": "...", "verdict": "ACCEPTED"}
"""

from abc import ABC, abstractmethod


class BaseAIValidator(ABC):
    """Abstract base class for AI signal validation."""

    @abstractmethod
    def validate(self, signal: dict) -> dict:
        """
        Validate a raw signal dict and return an AI score.

        Parameters
        ----------
        signal : dict
            Raw signal from the SMC scanner (pattern, direction, bias, etc.)

        Returns
        -------
        dict
            {
                "score":     float,  # 0.0–10.0
                "reasoning": str,    # Human-readable rationale
                "verdict":   str,    # "ACCEPTED" | "REJECTED"
            }
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the local LLM model is reachable."""
        ...
