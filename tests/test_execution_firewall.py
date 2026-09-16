from src.core.execution_firewall import ExecutionFirewall

def test_firewall_blocks_naked_orders():
    approved, reason = ExecutionFirewall.audit_trade_request(
        symbol="BTC/USD",
        side="buy",
        stop_loss=None,  # Naked order
        take_profit=88000.0,
        ai_score=9.0
    )
    assert not approved
    assert "Zero naked orders allowed" in reason

def test_firewall_blocks_sub_8_ai_scores():
    approved, reason = ExecutionFirewall.audit_trade_request(
        symbol="ETH/USD",
        side="buy",
        stop_loss=2400.0,
        take_profit=2500.0,
        ai_score=7.2,  # Sub-8.0 score
        bypass_killzone=True
    )
    assert not approved
    assert "below the mandatory 8.0/10.0 threshold" in reason

def test_firewall_blocks_5m_candle_bypasses():
    approved, reason = ExecutionFirewall.audit_trade_request(
        symbol="ETH/USD",
        side="buy",
        stop_loss=2400.0,
        take_profit=2500.0,
        ai_score=9.5,
        is_htf_confirmed=False,  # No 1H HTF confirmation
        bypass_killzone=True
    )
    assert not approved
    assert "Single 5-minute candle bypasses are prohibited" in reason

def test_firewall_approves_valid_master_trade():
    approved, reason = ExecutionFirewall.audit_trade_request(
        symbol="BTC/USD",
        side="buy",
        stop_loss=82000.0,
        take_profit=86000.0,
        ai_score=9.2,
        is_htf_confirmed=True,
        bypass_killzone=True,
        bypass_cooldown=True,
        bypass_circuit_breaker=True
    )
    assert approved
    assert reason == "APPROVED_BY_FIREWALL"
