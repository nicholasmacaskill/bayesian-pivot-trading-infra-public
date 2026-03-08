import os
import json
import numpy as np
import pandas as pd
from google import genai
from src.core.config import Config

class AIValidator:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
            
        # Load ICT Oracle Knowledge Base (Attempt Sovereign Core first)
        self.kb_path = os.path.join(os.getcwd(), "src", "sovereign_core", "ict_oracle_kb.json")
        if not os.path.exists(self.kb_path):
            self.kb_path = os.path.join(os.path.dirname(__file__), "ict_oracle_kb.json")
            
        self.oracle_kb = {}
        if os.path.exists(self.kb_path):
            try:
                with open(self.kb_path, 'r') as f:
                    self.oracle_kb = json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load Oracle KB: {e}")

        # Load Sovereign Prompts (Private IP)
        try:
            from src.sovereign_core.prompts.validator_prompts import SOVEREIGN_VALIDATOR_PROMPT, SOVEREIGN_VISION_PROMPT
            self.sovereign_prompt = SOVEREIGN_VALIDATOR_PROMPT
            self.sovereign_vision = SOVEREIGN_VISION_PROMPT
            self.is_lite = False
        except ImportError:
            self.sovereign_prompt = None
            self.sovereign_vision = None
            self.is_lite = True

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
    
    def detect_market_regime(self, df):
        """
        Classifies current market regime based on volatility and trend characteristics.
        
        Returns:
            str: Regime classification (High-Volatility Expansion, Low-Volatility Consolidation, etc.)
        """
        if df is None or len(df) < 50:
            return "Unknown (Insufficient Data)"
        
        try:
            # Calculate ATR
            high = df['high']
            low = df['low']
            close = df['close']
            
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
            atr = tr.rolling(window=14).mean()
            
            current_atr = atr.iloc[-1]
            mean_atr = atr.iloc[-50:].mean()
            
            # Volatility classification
            if pd.isna(current_atr) or pd.isna(mean_atr):
                return "Unknown (ATR Calculation Failed)"
            
            vol_ratio = current_atr / mean_atr if mean_atr > 0 else 1.0
            
            # Trend detection (simple EMA cross)
            ema_20 = close.ewm(span=20).mean().iloc[-1]
            ema_50 = close.ewm(span=50).mean().iloc[-1]
            
            # Range analysis (last 20 candles)
            recent_high = df['high'].iloc[-20:].max()
            recent_low = df['low'].iloc[-20:].min()
            range_pct = (recent_high - recent_low) / recent_low if recent_low > 0 else 0
            
            # Classification logic
            if vol_ratio > 1.3: # Loosened from 1.5
                if ema_20 > ema_50 * 1.01 or ema_20 < ema_50 * 0.99:
                    return "Trending Expansion" # Renamed for clarity
                else:
                    return "High-Volatility Expansion"
            elif vol_ratio < 0.9:
                # --- REGIME GUARD: Strict Consolidation Check ---
                # Even if vol is low, if we broke a 20-candle high, we are NOT in consolidation
                if close.iloc[-1] > recent_high or close.iloc[-1] < recent_low:
                    return "Consolidation Breakout (Expansion)"

                if range_pct < 0.015:  # Tightened from 2%
                    return "Low-Volatility Consolidation"
                else:
                    return "Low-Volatility Ranging"
            else:
                if abs(ema_20 - ema_50) / ema_50 < 0.005: # Tightened from 0.01
                    return "Normal-Volatility Choppy"
                else:
                    return "Normal-Volatility Trending"
                    
        except Exception as e:
            print(f"⚠️ Regime detection failed: {e}")
            return "Unknown (Error)"
    
    def calculate_dynamic_risk(self, score, regime, news_context):
        """
        Calculates suggested risk multiplier based on score, regime, and news.
        
        Args:
            score: AI confidence score (0-10)
            regime: Market regime classification
            news_context: News context string
            
        Returns:
            dict: Contains multiplier and suggested_risk_pct
        """
        base_risk = 0.0075  # 0.75% (fixed for live execution)
        multiplier = 1.0
        reasoning = []
        
        # High confidence + Low volatility = Increase size
        if score >= 8.5 and "Low-Volatility" in regime:
            multiplier = 1.33  # Increase to 1.0%
            reasoning.append("High score (≥8.5) + Low volatility = Increase to 1.0%")
        
        # Low confidence OR high-impact news = Decrease size
        elif score < 8.0:
            multiplier = 0.53  # Decrease to 0.40%
            reasoning.append("Low score (<8.0) = Decrease to 0.40%")
        
        elif "ACTIVE EVENT" in news_context:
            multiplier = 0.53  # Decrease to 0.40%
            reasoning.append("High-impact news event = Decrease to 0.40%")
        
        # High volatility = Slight decrease for safety
        elif "High-Volatility" in regime:
            multiplier = 0.87  # Decrease to 0.65%
            reasoning.append("High volatility = Slight decrease to 0.65%")
        
        else:
            reasoning.append("Normal conditions = Maintain 0.75%")
        
        return {
            "multiplier": round(multiplier, 2),
            "suggested_risk_pct": round(base_risk * multiplier * 100, 2),
            "reasoning": " | ".join(reasoning)
        }
    
    def estimate_slippage(self, symbol, entry_price, position_size, exchange=None):
        """
        Estimates slippage based on L2 order book depth.
        
        Args:
            symbol: Trading pair
            entry_price: Intended entry price
            position_size: Position size in base currency
            exchange: CCXT exchange instance (optional)
            
        Returns:
            dict: Contains slippage estimate and quality rating
        """
        if exchange is None:
            return {
                "slippage_pct": None,
                "quality": "Unknown",
                "reasoning": "Order book unavailable"
            }
        
        try:
            order_book = exchange.fetch_order_book(symbol, limit=50)
            
            # Determine direction based on position size sign
            if position_size > 0:  # Buying
                asks = order_book['asks']
                cumulative_volume = 0
                total_cost = 0
                
                for price, volume in asks:
                    if cumulative_volume >= position_size:
                        break
                    fill_volume = min(volume, position_size - cumulative_volume)
                    total_cost += price * fill_volume
                    cumulative_volume += fill_volume
                
                if cumulative_volume > 0:
                    avg_fill_price = total_cost / cumulative_volume
                    slippage_pct = ((avg_fill_price - entry_price) / entry_price) * 100
                else:
                    slippage_pct = None
                    
            else:  # Selling
                bids = order_book['bids']
                cumulative_volume = 0
                total_proceeds = 0
                abs_position = abs(position_size)
                
                for price, volume in bids:
                    if cumulative_volume >= abs_position:
                        break
                    fill_volume = min(volume, abs_position - cumulative_volume)
                    total_proceeds += price * fill_volume
                    cumulative_volume += fill_volume
                
                if cumulative_volume > 0:
                    avg_fill_price = total_proceeds / cumulative_volume
                    slippage_pct = ((entry_price - avg_fill_price) / entry_price) * 100
                else:
                    slippage_pct = None
            
            # Quality rating
            if slippage_pct is None:
                quality = "Unknown"
                reasoning = "Insufficient liquidity data"
            elif slippage_pct < 0.05:
                quality = "Excellent"
                reasoning = "Deep liquidity, minimal slippage expected"
            elif slippage_pct < 0.15:
                quality = "Acceptable"
                reasoning = "Moderate liquidity, acceptable slippage"
            else:
                quality = "Poor"
                reasoning = "Shallow liquidity, high slippage risk"
            
            return {
                "slippage_pct": round(slippage_pct, 3) if slippage_pct else None,
                "quality": quality,
                "reasoning": reasoning
            }
            
        except Exception as e:
            print(f"⚠️ Slippage estimation failed: {e}")
            return {
                "slippage_pct": None,
                "quality": "Unknown",
                "reasoning": f"Error: {str(e)}"
            }

    def hard_logic_audit(self, setup, df=None):
        """
        Air-Gapped Fallback: Mathematical validation when AI is unavailable.
        Now includes dual-track output.
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
        
        # Detect regime for shadow track
        regime = self.detect_market_regime(df) if df is not None else "Unknown"
        news_context = setup.get('news_context', 'Clear')
        risk_calc = self.calculate_dynamic_risk(score, regime, news_context)
        
        return {
            "live_execution": {
                "score": float(score),
                "verdict": "HARD_LOGIC_PASS" if score >= 7 else "HARD_LOGIC_REJECT",
                "reasoning": f"FALLBACK MODE: {' | '.join(reasoning_parts)}. Score: {score}/10",
                "execution_logic": "Standard 1:3 RR with tight SL at invalidation point",
                "discipline_check": "Air-gapped audit - AI unavailable"
            },
            "shadow_optimizer": {
                "suggested_risk_multiplier": risk_calc['multiplier'],
                "regime_classification": regime,
                "alpha_delta_prediction": "N/A (Fallback mode)",
                "slippage_estimate": "N/A",
                "optimization_reasoning": risk_calc['reasoning']
            }
        }

    def analyze_trade(self, setup, sentiment, whales, image_path=None, df=None, exchange=None, memory_context=None, regime_str=None):
        """
        Calls Gemini API to validate the setup with DUAL-TRACK analysis.
        
        Args:
            setup: Trade setup dict
            sentiment: Market sentiment data
            whales: Whale activity data
            image_path: Optional chart image path
            df: Optional dataframe for regime detection
            exchange: Optional CCXT exchange for slippage estimation
            memory_context: Optional historical context from RAG
            regime_str: Optional pre-calculated regime override (Ground Truth)
        
        Returns:
            dict: Dual-track analysis with live_execution and shadow_optimizer sections
        """
        if not self.client:
            # Fallback to hard logic if AI unavailable
            return self.hard_logic_audit(setup, df)

        # Dynamic Oracle Grounding
        oracle_rules = self._get_oracle_prompt(setup.get('pattern', 'PO3'))
        
        # Detect market regime for shadow track (Use override if provided)
        regime = regime_str if regime_str else (self.detect_market_regime(df) if df is not None else "Unknown")
        
        # Calculate slippage estimate
        entry_price = setup.get('entry', 0)
        position_size = setup.get('position_size_estimate', 1.0)  # Estimate for slippage calc
        slippage_info = self.estimate_slippage(
            setup['symbol'], 
            entry_price, 
            position_size, 
            exchange
        )

        # DUAL-TRACK PROMPT CONSTRUCTION
        if self.sovereign_prompt:
            # Full Sovereign Version (Master Theory active)
            prompt = self.sovereign_prompt.format(
                symbol=setup['symbol'],
                pattern=setup.get('pattern', 'SMC Logic'),
                phase=setup.get('time_quartile', {}).get('phase', 'Unknown'),
                position='Deep Discount' if setup.get('is_discount') else 'Premium' if setup.get('is_premium') else 'Neutral',
                smt_strength=setup.get('smt_strength', 0),
                min_smt=Config.MIN_SMT_STRENGTH,
                cross_asset=setup.get('cross_asset_divergence', 0),
                bias=setup.get('bias', 'Neutral'),
                news=setup.get('news_context', 'Clear'),
                sentiment=sentiment,
                whales=whales,
                regime=regime,
                slippage_pct=slippage_info.get('slippage_pct', 'N/A'),
                slippage_quality=slippage_info.get('quality', 'Unknown'),
                threshold=Config.AI_THRESHOLD,
                memory_context=memory_context or "No highly similar historical setups found for reference."
            ).replace("[ORACLE_RULES_PLACEHOLDER]", oracle_rules)
        else:
            # Public Lite Version (General ICT logic)
            prompt = f"""
            YOU ARE AN INSTITUTIONAL RISK MANAGER (ICT PHILOSOPHY).
            Analyze this trade setup using Standard ICT concepts (PO3, FVG, SMT).
            
            ### GOAL: Identify if this setup aligns with institutional expansion or retail inducement.
            
            - Pattern: {setup.get('pattern', 'SMC Logic')}
            - SMT Strength: {setup.get('smt_strength', 0)} (Institutional Divergence Score)
            - True SMT Type: {setup.get('true_smt', 'None detected')}
            - TECHNICAL REGIME: {regime} (THIS IS GROUND TRUTH - DO NOT HALLUCINATE CONSOLIDATION IF THIS SAYS TRENDING/EXPANSION)
            - Confluences: {oracle_rules}
            
            NOTE: SMT Strength > 0.35 indicates a 'Crack in Correlation' (Institutional Sponsorship). 
            Even if direct trend alignment is neutral, a strong SMT suggests institutions are actively masking their move.
            
            Verdict Options: FLOW_GO, REJECTED, INDUCEMENT_WARNING.
            """

        if image_path:
            if self.sovereign_vision:
                prompt += self.sovereign_vision
            else:
                prompt += "\nAnalysis of attached chart image requested for ICT confluence."

        prompt += """
        ### OUTPUT FORMAT (STRICT JSON):
        Return EXACTLY this structure:
        {{
            "live_execution": {{
                "score": <0.0-10.0>,
                "verdict": "<FLOW_GO | REJECTED | INDUCEMENT_WARNING>",
                "reasoning": "<Cite specific Oracle rules and confluence>",
                "execution_logic": "<SL/TP adjustments>",
                "discipline_check": "<Strategy drift warnings>"
            }},
            "shadow_optimizer": {{
                "suggested_risk_multiplier": <e.g., 1.33 or 0.53>,
                "regime_classification": "<Confirm or refine: {regime}>",
                "alpha_delta_prediction": "<Quantify expected improvement/degradation vs control>",
                "slippage_estimate": "<{slippage_info.get('slippage_pct', 'N/A')}%>",
                "optimization_reasoning": "<Why this multiplier? What regime signals support it?>"
            }}
        }}
        
        CRITICAL: Return ONLY valid JSON. No markdown, no explanations outside the JSON structure.
        """

        try:
            # For development, return simulated result if key is 'MOCK'
            if self.api_key == "MOCK":
                return {
                    "live_execution": {
                        "score": 9.2,
                        "verdict": "FLOW_GO",
                        "reasoning": f"MOCK: {setup.get('pattern')} confirmed with Strong SMT (>0.35) and Deep Discount. Sniper criteria met.",
                        "execution_logic": "Execute at FVG with 1:3 RR",
                        "discipline_check": "Institutional Grade Setup"
                    },
                    "shadow_optimizer": {
                        "suggested_risk_multiplier": 1.25,
                        "regime_classification": regime,
                        "alpha_delta_prediction": "+20% vs control (High Precision)",
                        "slippage_estimate": f"{slippage_info.get('slippage_pct', 'N/A')}%",
                        "optimization_reasoning": "Score >9.0 + Low-Volatility = Aggressive 1.25x Size"
                    }
                }

            contents = [prompt]
            if image_path and os.path.exists(image_path):
                from PIL import Image
                img = Image.open(image_path)
                contents.append(img)

            import time
            max_retries = 3
            base_delay = 5
            
            text = None
            last_err = None
            
            # NEXT-GEN MULTI-TRY LOGIC WITH EXPONENTIAL BACKOFF
            models_to_try = [
                'gemini-2.0-flash',     # Confirmed working
                'gemini-2.5-flash',     # Latest generation fallback
                'gemini-1.5-flash',     # Reliable last resort
            ]
            
            for model_name in models_to_try:
                for attempt in range(max_retries):
                    try:
                        response = self.client.models.generate_content(
                            model=model_name, 
                            contents=contents
                        )
                        text = response.text
                        break # Success for this model
                    except Exception as e:
                        last_err = e
                        err_str = str(e)
                        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            if attempt < max_retries - 1:
                                delay = base_delay * (2 ** attempt)
                                print(f"⚠️ AI Validator 429 Rate Limit ({model_name}). Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                                time.sleep(delay)
                                continue
                        
                        # If not a 429 or max retries reached, break out of the retry loop to try the next model
                        if "404" not in err_str and "NOT_FOUND" not in err_str:
                            break
                            
                if text:
                    break # Success overall
            
            if not text:
                raise last_err or Exception("All Gemini models failed even with retries")
            
            # Extract JSON from response (Robust extraction)
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                try:
                    result = json.loads(json_match.group())
                    # Validate structure
                    if 'live_execution' not in result or 'shadow_optimizer' not in result:
                        print("⚠️ AI returned incomplete dual-track structure. Using fallback.")
                        return self.hard_logic_audit(setup, df)
                    return result
                except json.JSONDecodeError:
                    print(f"⚠️ AI returned invalid JSON. Raw output first 100 chars: {text[:100]}...")
                    return self.hard_logic_audit(setup, df)
            else:
                print(f"⚠️ AI Output Parsing Error (No JSON block found). Raw output first 100 chars: {text[:100]}...")
                return self.hard_logic_audit(setup, df)
                
        except Exception as e:
            print(f"⚠️ AI Timeout/Error: {e}. Switching to HARD LOGIC FALLBACK.")
            return self.hard_logic_audit(setup, df)

    def get_visual_bias(self, image_path):
        """
        VISION AUDIT: Determines Trend Bias from Chart Image.
        Returns: +1 (Bullish), -1 (Bearish), 0 (Neutral)
        """
        if not self.client or not image_path or not os.path.exists(image_path):
            return 0
            
        prompt = """
        ACT AS A PROFESSIONAL TECHNICAL ANALYST.
        Analyze this 4H Market Structure Chart.
        
        Focus on:
        1. EMA 20 (Green) vs EMA 50 (Red) Slope and Separation.
        2. Market Structure (Higher Highs/Lows vs Lower Highs/Lows).
        
        VERDICT OPTIONS:
        - BULLISH (Green over Red, Higher Highs)
        - BEARISH (Red over Green, Lower Lows)
        - NEUTRAL (Choppy, EMAs flat/twisting)
        
        Return ONLY one word: BULLISH, BEARISH, or NEUTRAL.
        """
        
        try:
            from PIL import Image
            img = Image.open(image_path)
            
            import time
            max_retries = 3
            base_delay = 5
            
            # NEXT-GEN MULTI-TRY LOGIC (VISION) WITH EXPONENTIAL BACKOFF
            models_to_try = [
                'gemini-2.0-flash',     # Confirmed working, vision-capable
                'gemini-2.5-flash',     # Latest generation fallback
                'gemini-1.5-flash',     # Reliable last resort
            ]
            
            verdict = "NEUTRAL"
            success = False
            for model_name in models_to_try:
                for attempt in range(max_retries):
                    try:
                        response = self.client.models.generate_content(
                            model=model_name, 
                            contents=[prompt, img]
                        )
                        verdict = response.text.upper().strip()
                        success = True
                        break
                    except Exception as e:
                        err_str = str(e)
                        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            if attempt < max_retries - 1:
                                delay = base_delay * (2 ** attempt)
                                print(f"⚠️ Visual Bias Rate Limit ({model_name}). Retrying in {delay}s... (Attempt {attempt+1}/{max_retries})")
                                time.sleep(delay)
                                continue
                                
                        if "404" not in err_str and "NOT_FOUND" not in err_str:
                            break
                            
                if success:
                    break
            
            if "BULLISH" in verdict: return 1
            if "BEARISH" in verdict: return -1
            return 0
            
        except Exception as e:
            print(f"⚠️ Visual Bias Check Failed: {e}")
            return 0

def validate_setup(setup, sentiment, whales, image_path=None, df=None, exchange=None, memory_context=None, regime_str=None):
    """
    Main entry point for trade validation with dual-track analysis.
    
    Args:
        setup: Trade setup dict
        sentiment: Market sentiment data
        whales: Whale activity data
        image_path: Optional chart image path
        df: Optional dataframe for regime detection
        exchange: Optional CCXT exchange for slippage estimation
        memory_context: Optional historical context from RAG
        regime_str: Optional pre-calculated regime override
    
    Returns:
        dict: Dual-track analysis result
    """
    validator = AIValidator()
    return validator.analyze_trade(setup, sentiment, whales, image_path, df, exchange, memory_context, regime_str)
