import os
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple

logger = logging.getLogger(__name__)

@dataclass
class AccountValidatorProfile:
    account_key: str                     # e.g. 'ACCOUNT_A'
    account_name: str                    # e.g. 'Conservative Sovereign Anchor'
    email_env_key: str                   # e.g. 'TRADELOCKER_EMAIL_A'
    strategy_mode: str                   # 'CONSERVATIVE', 'TREND', 'REVERSAL'
    hurst_chaos_range: Tuple[float, float] = (0.45, 0.55)
    hurst_required_mode: Optional[str] = None  # 'TREND_ONLY', 'REVERSAL_ONLY', None
    ai_threshold: float = 7.5
    bypass_ai_gate: bool = False
    require_smt_divergence: bool = False
    min_smt_strength: float = 0.15
    calendar_blackout_mins: int = 15
    slippage_atr_max: float = 1.5
    correlation_gate_active: bool = True
    target_rr_multiple: float = 2.5
    risk_per_trade: float = 0.005
    max_risk_usd: float = 125.0

def align_lot_size(qty: float, min_lot: float = 0.01, lot_step: float = 0.01, max_lot: float = 100.0) -> float:
    """
    Aligns raw lot quantity with broker metadata constraints (min_lot, lot_step, max_lot).
    Rounds down to prevent exceeding theoretical risk caps.
    """
    if qty < min_lot:
        return 0.0
    steps = int((qty - min_lot) / lot_step)
    aligned = min_lot + (steps * lot_step)
    return round(min(aligned, max_lot), 4)

class MultiAccountFunnelManager:
    """
    Manages tailored Funnel Validator profiles across all live TradeLocker accounts.
    Evaluates candidate trade setups against per-account filter combinations.
    """
    def __init__(self):
        self._intent_lock = threading.Lock()
        self._pending_intents = {}  # key: (norm_symbol, norm_dir, account_key) -> timestamp
        self.profiles: Dict[str, AccountValidatorProfile] = {
            "ACCOUNT_A": AccountValidatorProfile(
                account_key="ACCOUNT_A",
                account_name="Conservative Sovereign Anchor",
                email_env_key="TRADELOCKER_EMAIL_A",
                strategy_mode="CONSERVATIVE",
                hurst_chaos_range=(0.45, 0.55),
                hurst_required_mode=None,
                ai_threshold=7.0,
                bypass_ai_gate=False,
                require_smt_divergence=False,
                min_smt_strength=0.15,
                calendar_blackout_mins=30,
                slippage_atr_max=1.5,
                correlation_gate_active=True,
                target_rr_multiple=2.5,
                risk_per_trade=0.005,
                max_risk_usd=125.0
            ),
            "ACCOUNT_B": AccountValidatorProfile(
                account_key="ACCOUNT_B",
                account_name="Volume Expansion Operator",
                email_env_key="TRADELOCKER_EMAIL_B",
                strategy_mode="TREND",
                hurst_chaos_range=(0.45, 0.55),
                hurst_required_mode="TREND_ONLY",
                ai_threshold=7.0,
                bypass_ai_gate=False,
                require_smt_divergence=False,
                min_smt_strength=0.15,
                calendar_blackout_mins=15,
                slippage_atr_max=2.0,
                correlation_gate_active=True,
                target_rr_multiple=3.0,
                risk_per_trade=0.005,
                max_risk_usd=250.0
            ),
            "ACCOUNT_C": AccountValidatorProfile(
                account_key="ACCOUNT_C",
                account_name="Turtle Soup Fader",
                email_env_key="TRADELOCKER_EMAIL_C",
                strategy_mode="REVERSAL",
                hurst_chaos_range=(0.45, 0.55),
                hurst_required_mode="REVERSAL_ONLY",
                ai_threshold=7.0,
                bypass_ai_gate=False,
                require_smt_divergence=False,
                min_smt_strength=0.15,
                calendar_blackout_mins=30,
                slippage_atr_max=1.5,
                correlation_gate_active=True,
                target_rr_multiple=2.5,
                risk_per_trade=0.005,
                max_risk_usd=125.0
            ),
            "ACCOUNT_D": AccountValidatorProfile(
                account_key="ACCOUNT_D",
                account_name="Liquidity Reversal Operator",
                email_env_key="TRADELOCKER_EMAIL_D",
                strategy_mode="REVERSAL",
                hurst_chaos_range=(0.45, 0.55),
                hurst_required_mode="REVERSAL_ONLY",
                ai_threshold=7.0,
                bypass_ai_gate=False,
                require_smt_divergence=False,
                min_smt_strength=0.15,
                calendar_blackout_mins=15,
                slippage_atr_max=1.5,
                correlation_gate_active=False,
                target_rr_multiple=2.5,
                risk_per_trade=0.005,
                max_risk_usd=65.0
            ),
            "ACCOUNT_E": AccountValidatorProfile(
                account_key="ACCOUNT_E",
                account_name="High Alpha Reversal Scalper",
                email_env_key="TRADELOCKER_EMAIL_E",
                strategy_mode="REVERSAL",
                hurst_chaos_range=(0.45, 0.55),
                hurst_required_mode="REVERSAL_ONLY",
                ai_threshold=7.0,
                bypass_ai_gate=False,
                require_smt_divergence=False,
                min_smt_strength=0.15,
                calendar_blackout_mins=15,
                slippage_atr_max=2.0,
                correlation_gate_active=False,
                target_rr_multiple=2.5,
                risk_per_trade=0.006,
                max_risk_usd=65.0
            ),
            "ACCOUNT_F": AccountValidatorProfile(
                account_key="ACCOUNT_F",
                account_name="50k Oracle Instant Operator",
                email_env_key="TRADELOCKER_EMAIL_F",
                strategy_mode="TREND",
                hurst_chaos_range=(0.45, 0.55),
                hurst_required_mode="TREND_ONLY",
                ai_threshold=7.0,
                bypass_ai_gate=False,
                require_smt_divergence=False,
                min_smt_strength=0.15,
                calendar_blackout_mins=15,
                slippage_atr_max=2.0,
                correlation_gate_active=True,
                target_rr_multiple=3.0,
                risk_per_trade=0.005,
                max_risk_usd=250.0
            ),
            "ACCOUNT_G": AccountValidatorProfile(
                account_key="ACCOUNT_G",
                account_name="25k Oracle Instant Operator",
                email_env_key="TRADELOCKER_EMAIL_G",
                strategy_mode="CONSERVATIVE",
                hurst_chaos_range=(0.45, 0.55),
                hurst_required_mode=None,
                ai_threshold=7.0,
                bypass_ai_gate=False,
                require_smt_divergence=False,
                min_smt_strength=0.15,
                calendar_blackout_mins=30,
                slippage_atr_max=1.5,
                correlation_gate_active=True,
                target_rr_multiple=2.5,
                risk_per_trade=0.005,
                max_risk_usd=125.0
            ),
            "ACCOUNT_H": AccountValidatorProfile(
                account_key="ACCOUNT_H",
                account_name="10k Oracle Instant Operator",
                email_env_key="TRADELOCKER_EMAIL_H",
                strategy_mode="REVERSAL",
                hurst_chaos_range=(0.45, 0.55),
                hurst_required_mode="REVERSAL_ONLY",
                ai_threshold=7.0,
                bypass_ai_gate=False,
                require_smt_divergence=False,
                min_smt_strength=0.15,
                calendar_blackout_mins=15,
                slippage_atr_max=1.5,
                correlation_gate_active=False,
                target_rr_multiple=2.5,
                risk_per_trade=0.005,
                max_risk_usd=65.0
            ),
            "ACCOUNT_I": AccountValidatorProfile(
                account_key="ACCOUNT_I",
                account_name="Judas Inducement & Macro Operator",
                email_env_key="TRADELOCKER_EMAIL_I",
                strategy_mode="REVERSAL",
                hurst_chaos_range=(0.45, 0.55),
                hurst_required_mode=None,
                ai_threshold=7.0,
                bypass_ai_gate=False,
                require_smt_divergence=False,
                min_smt_strength=0.15,
                calendar_blackout_mins=15,
                slippage_atr_max=2.0,
                correlation_gate_active=False,
                target_rr_multiple=2.5,
                risk_per_trade=0.005,
                max_risk_usd=65.0
            ),
        }

    def register_in_flight_intent(self, symbol: str, direction: str, account_key: str):
        """Registers a pending order intent in-flight before HTTP API dispatch."""
        norm_symbol = (symbol or "").replace("/", "").replace("_", "").upper()
        norm_dir = str(direction or "BUY").upper()
        with self._intent_lock:
            self._pending_intents[(norm_symbol, norm_dir, account_key)] = time.time()

    def clear_in_flight_intent(self, symbol: str, direction: str, account_key: str):
        """Clears a pending order intent after API completion or failure."""
        norm_symbol = (symbol or "").replace("/", "").replace("_", "").upper()
        norm_dir = str(direction or "BUY").upper()
        with self._intent_lock:
            self._pending_intents.pop((norm_symbol, norm_dir, account_key), None)

    def check_anti_hedging_gate(
        self,
        setup_symbol: str,
        setup_direction: str,
        open_positions: List[dict],
        account_key: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Anti-hedging and duplicate intent protection gate.
        """
        norm_symbol = (setup_symbol or "").replace("/", "").replace("_", "").upper()
        norm_dir = str(setup_direction or "BUY").upper()
        opp_dir = "SELL" if norm_dir == "BUY" else "BUY"

        # 1. In-flight intent check
        if account_key:
            with self._intent_lock:
                if (norm_symbol, norm_dir, account_key) in self._pending_intents:
                    return False, f"IN_FLIGHT_ORDER_INTENT_ACTIVE for {account_key}"

        # 2. Existing position opposite check
        for pos in open_positions:
            pos_sym = str(pos.get("symbol", "")).replace("/", "").replace("_", "").upper()
            pos_side = str(pos.get("side", "")).upper()

            if pos_sym == norm_symbol:
                if pos_side == opp_dir:
                    return False, f"ANTI_HEDGING_VIOLATION: Existing {pos_side} position active on {norm_symbol}."
                if pos_side == norm_dir:
                    return False, f"DUPLICATE_POSITION_EXPOSURE: Existing {pos_side} position already open."

        return True, None

    def evaluate_account_eligibility(
        self,
        account_key: str,
        setup: dict,
        hurst: float,
        smt_strength: float,
        ai_score: float,
        slippage_ratio: float,
        cal_safe: bool,
        corr_ok: bool,
        regime_allowed: bool
    ) -> Tuple[bool, List[str]]:
        """
        Evaluates a candidate trade against a specific account's validator profile.
        Returns: (passed: bool, rejection_reasons: List[str])
        """
        profile = self.profiles.get(account_key)
        if not profile:
            return False, [f"UNKNOWN_ACCOUNT_KEY ({account_key})"]

        rejection_reasons = []

        # 1. Hurst Gate Check
        h_low, h_high = profile.hurst_chaos_range
        if h_low <= hurst <= h_high:
            rejection_reasons.append(f"HURST_CHAOS_GATE ({hurst:.3f} in range [{h_low}, {h_high}])")
        elif profile.hurst_required_mode == "TREND_ONLY" and hurst <= 0.55:
            rejection_reasons.append(f"HURST_NOT_TRENDING ({hurst:.3f} <= 0.55)")
        elif profile.hurst_required_mode == "REVERSAL_ONLY" and hurst >= 0.45:
            rejection_reasons.append(f"HURST_NOT_REVERSAL ({hurst:.3f} >= 0.45)")

        # 2. Calendar / News Gate Check
        if profile.calendar_blackout_mins > 0 and not cal_safe:
            rejection_reasons.append(f"CALENDAR_BLACKOUT ({profile.calendar_blackout_mins}m rule)")

        # 3. Slippage Floor Check
        if slippage_ratio > profile.slippage_atr_max:
            rejection_reasons.append(f"SLIPPAGE_ATR_BREACH ({slippage_ratio:.2f} > {profile.slippage_atr_max})")

        # 4. Correlation Gate Check
        if profile.correlation_gate_active and not corr_ok:
            rejection_reasons.append("CORRELATION_CAP_REACHED")

        # 5. Regime Filter Check
        if not regime_allowed:
            rejection_reasons.append("REGIME_FILTER_BLOCKED")

        # 6. SMT Divergence Dynamic Confluence Booster
        effective_ai_score = ai_score
        if smt_strength >= profile.min_smt_strength:
            effective_ai_score = min(10.0, ai_score + 1.0)
            logger.info(f"✨ SMT Divergence Booster (+1.0) applied for {profile.account_name}: {ai_score:.1f} -> {effective_ai_score:.1f}")
        elif profile.require_smt_divergence and smt_strength < profile.min_smt_strength:
            rejection_reasons.append(f"INSUFFICIENT_SMT ({smt_strength:.2f} < {profile.min_smt_strength})")

        # 7. AI Conviction Score Check
        if not profile.bypass_ai_gate:
            if effective_ai_score < profile.ai_threshold:
                rejection_reasons.append(f"AI_SCORE_BELOW_THRESHOLD ({effective_ai_score:.1f} < {profile.ai_threshold})")

        passed = len(rejection_reasons) == 0
        return passed, rejection_reasons

    def evaluate_setup_for_account(
        self,
        setup: dict,
        account_key: str,
        hurst: float = 0.58,
        smt_strength: float = 0.20,
        slippage_ratio: float = 1.0,
        cal_safe: bool = True,
        corr_ok: bool = True,
        regime_allowed: bool = True,
        ai_score: float = 8.0,
        open_positions: Optional[List[dict]] = None
    ) -> Tuple[bool, List[str]]:
        """
        Evaluates a candidate setup against an account's validator profile, including anti-hedging.
        """
        profile = self.profiles.get(account_key)
        if not profile:
            return False, ["UNKNOWN_ACCOUNT_PROFILE"]

        rejection_reasons = []

        # 0. Portfolio Anti-Hedging Gate Check
        anti_hedge_ok, anti_hedge_reason = self.check_anti_hedging_gate(
            setup_symbol=setup.get('symbol', ''),
            setup_direction=setup.get('direction', 'BUY'),
            open_positions=open_positions or [],
            account_key=account_key
        )
        if not anti_hedge_ok:
            rejection_reasons.append(anti_hedge_reason)

        passed_elig, elig_reasons = self.evaluate_account_eligibility(
            account_key=account_key,
            setup=setup,
            hurst=hurst,
            smt_strength=smt_strength,
            ai_score=ai_score,
            slippage_ratio=slippage_ratio,
            cal_safe=cal_safe,
            corr_ok=corr_ok,
            regime_allowed=regime_allowed
        )
        rejection_reasons.extend(elig_reasons)

        return len(rejection_reasons) == 0, rejection_reasons
