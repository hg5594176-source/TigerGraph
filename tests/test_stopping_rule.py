"""
Unit Tests for Deterministic Stopping Rule
Verifies assess_uncertainty stopping rules:
1. Clear winner (margin >= threshold) -> confident
2. Evidence loop cap reached -> escalate
3. Policy immediate action flag -> policy_mandate
4. Multiple close hypotheses below cap -> None (gather more evidence)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent.nodes.assess_uncertainty import should_stop, CONFIDENCE_THRESHOLD, MAX_EVIDENCE_LOOPS


def test_clear_winner_stops_with_confident():
    """Rule 1: If top hypothesis leads second by >= threshold, stop with confident."""
    hypotheses = [
        {"typology_id": "TYP-01", "confidence": 0.85},
        {"typology_id": "TYP-02", "confidence": 0.35},
        {"typology_id": "TYP-03", "confidence": 0.20}
    ]
    reason = should_stop(hypotheses, evidence_count=1)
    assert reason == "confident", f"Expected 'confident', got '{reason}'"
    print("[PASS] test_clear_winner_stops_with_confident")


def test_evidence_cap_escalates():
    """Rule 2: If evidence loop reaches MAX_EVIDENCE_LOOPS, stop with escalate."""
    hypotheses = [
        {"typology_id": "TYP-01", "confidence": 0.52},
        {"typology_id": "TYP-02", "confidence": 0.49}
    ]
    reason = should_stop(hypotheses, evidence_count=MAX_EVIDENCE_LOOPS)
    assert reason == "escalate", f"Expected 'escalate', got '{reason}'"
    print("[PASS] test_evidence_cap_escalates")


def test_policy_mandate_stops_immediately():
    """Rule 3: If leading typology mandates immediate action, stop with policy_mandate."""
    from agent.nodes.assess_uncertainty import IMMEDIATE_ACTION_TYPOLOGIES
    if not IMMEDIATE_ACTION_TYPOLOGIES:
        IMMEDIATE_ACTION_TYPOLOGIES.add("TYP-01")

    immediate_typ = next(iter(IMMEDIATE_ACTION_TYPOLOGIES))
    hypotheses = [
        {"typology_id": immediate_typ, "confidence": 0.50},
        {"typology_id": "TYP-99", "confidence": 0.45}
    ]
    reason = should_stop(hypotheses, evidence_count=1, leading_typology=immediate_typ)
    assert reason == "policy_mandate", f"Expected 'policy_mandate', got '{reason}'"
    print("[PASS] test_policy_mandate_stops_immediately")


def test_close_hypotheses_continue_gathering():
    """Rule 4: When hypotheses are too close and cap not reached, return None to continue gathering."""
    hypotheses = [
        {"typology_id": "TYP-01", "confidence": 0.55},
        {"typology_id": "TYP-02", "confidence": 0.50}
    ]
    reason = should_stop(hypotheses, evidence_count=1)
    assert reason is None, f"Expected None (continue loop), got '{reason}'"
    print("[PASS] test_close_hypotheses_continue_gathering")


if __name__ == "__main__":
    test_clear_winner_stops_with_confident()
    test_evidence_cap_escalates()
    test_policy_mandate_stops_immediately()
    test_close_hypotheses_continue_gathering()
    print("All stopping rule tests PASSED successfully!")
