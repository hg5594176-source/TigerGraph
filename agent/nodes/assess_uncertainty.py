"""
Assess Uncertainty Node — Deterministic stopping rule.
Decides: act, gather more evidence, or escalate.
NOT an LLM judgment — implements literal stopping criteria.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState
from config import config

# Import policy rules for immediate-action detection
from data.load_policy import POLICY_RULES

# Hard-coded threshold and cap from config
CONFIDENCE_THRESHOLD = config.agent.confidence_threshold  # Default 0.25
MAX_EVIDENCE_LOOPS = config.agent.max_evidence_loops       # Default 5

# Policy rules that mandate immediate action
IMMEDIATE_ACTION_RULES = [r for r in POLICY_RULES if r.get("immediate_action", False)]
IMMEDIATE_ACTION_TYPOLOGIES = set()
for r in IMMEDIATE_ACTION_RULES:
    IMMEDIATE_ACTION_TYPOLOGIES.update(r.get("applies_to", []))


def should_stop(hypothesis_board: list[dict],
                evidence_count: int,
                leading_typology: str | None = None) -> str | None:
    """
    Deterministic stopping rule. Returns:
    - "confident": top confidence margin exceeds threshold
    - "escalate": hard evidence cap hit
    - "policy_mandate": policy mandates immediate action
    - None: continue gathering evidence

    This function is tested independently with synthetic data.
    """
    if not hypothesis_board:
        return None

    confidences = sorted(
        [h.get("confidence", 0) for h in hypothesis_board],
        reverse=True
    )

    # Rule 1: Clear winner — confidence gap exceeds threshold
    if len(confidences) >= 2:
        margin = confidences[0] - confidences[1]
        if margin >= CONFIDENCE_THRESHOLD:
            return "confident"

    # If only one hypothesis, check if it's above a hard threshold
    if len(confidences) == 1 and confidences[0] >= 0.7:
        return "confident"

    # Rule 2: Hard evidence cap — escalate to analyst
    if evidence_count >= MAX_EVIDENCE_LOOPS:
        return "escalate"

    # Rule 3: Policy mandates immediate action regardless of confidence
    if leading_typology and leading_typology in IMMEDIATE_ACTION_TYPOLOGIES:
        # Check if the leading confidence is at least moderate
        if confidences[0] >= 0.4:
            return "policy_mandate"

    return None  # Continue gathering


def assess_uncertainty(state: AgentState) -> dict:
    """
    Evaluate confidence margins and decide whether to stop or continue.
    This is a pure-logic node — no LLM call.
    """
    hypothesis_board = state.get("hypothesis_board", [])
    evidence_loop_count = state.get("evidence_loop_count", 0)
    leading_typology = state.get("leading_typology")

    stop_reason = should_stop(
        hypothesis_board=hypothesis_board,
        evidence_count=evidence_loop_count,
        leading_typology=leading_typology,
    )

    if stop_reason:
        print(f"  [assess_uncertainty] STOP: {stop_reason} "
              f"(loops={evidence_loop_count})")
    else:
        print(f"  [assess_uncertainty] CONTINUE gathering "
              f"(loops={evidence_loop_count}/{MAX_EVIDENCE_LOOPS})")

    # Log confidence margins for observability
    if hypothesis_board:
        sorted_hyps = sorted(hypothesis_board,
                             key=lambda h: h.get("confidence", 0), reverse=True)
        for h in sorted_hyps:
            print(f"    {h['typology_name']}: {h['confidence']:.3f}")

    return {
        "stop_reason": stop_reason,
    }
