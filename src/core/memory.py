import logging
import json
from datetime import datetime
from src.core.config import Config
from ai_audit_engine import AIAuditEngine
from src.core.supabase_client import supabase

logger = logging.getLogger(__name__)

class SetupMemory:
    """
    RAG Engine for Trading Setups.
    Translates raw data into technical narratives and performs semantic search.
    """
    def __init__(self, audit_engine=None):
        self.ai = audit_engine or AIAuditEngine()
        self.sb = supabase

    def textualize_setup(self, setup):
        """
        Converts a technical setup dict into a descriptive string for embedding.
        """
        try:
            symbol = setup.get('symbol', 'Unknown')
            pattern = setup.get('pattern', 'Unknown')
            direction = setup.get('direction', 'Unknown')
            smt = setup.get('smt_strength', 0.0)
            
            # Extract Session Phase
            quartile = setup.get('time_quartile', {})
            phase = quartile.get('phase', 'Unknown') if isinstance(quartile, dict) else "Unknown"
            
            # Index Context
            index_context = setup.get('index_context', 'Neutral')
            
            # Construct Technical Narrative
            narrative = (
                f"{symbol} {direction} Setup: {pattern}. "
                f"Market Phase: {phase}. "
                f"SMT Confluence: {smt}. "
                f"Intermarket Context: {index_context}. "
                f"News: {setup.get('news_context', 'Checked')}."
            )
            
            # Add price quartile context if available
            pq = setup.get('price_quartiles', {})
            if pq:
                narrative += f" Institutional Pricing: {json.dumps(pq)}."
                
            return narrative
        except Exception as e:
            logger.error(f"Error textualizing setup: {e}")
            return f"Trade Setup for {setup.get('symbol', 'Unknown')}"

    def find_similar_setups(self, setup, match_count=3, threshold=0.7):
        """
        Searches historical journal and scans for similar setups.
        """
        if not self.sb.client:
            return []

        text = self.textualize_setup(setup)
        embedding = self.ai.get_text_embedding(text)
        
        if not embedding:
            return []

        try:
            # Match against Journal (Real Executions)
            # This uses the RPC function created in init_vector_db.py
            res = self.sb.client.rpc('match_trades', {
                'query_embedding': embedding,
                'match_threshold': threshold,
                'match_count': match_count
            }).execute()
            
            return res.data or []
        except Exception as e:
            logger.error(f"Semantic Search Error: {e}")
            return []

    def get_context_for_validator(self, setup):
        """
        Prepares a context string for the AI Validator based on memory.
        """
        similar = self.find_similar_setups(setup)
        if not similar:
            return "MEMORY: No highly similar historical setups found for reference."

        context = "MEMORY: Found similar historical setups:\n"
        for i, trade in enumerate(similar, 1):
            pnl_status = "WIN" if trade.get('pnl', 0) > 0 else "LOSS"
            context += (
                f"{i}. [{trade.get('symbol')}] Result: {pnl_status} (${trade.get('pnl')}). "
                f"AI Grade: {trade.get('ai_grade')}/10. "
                f"Feedback: {trade.get('notes') or 'No notes.'}\n"
            )
        
        return context

# Singleton instance
memory = SetupMemory()
