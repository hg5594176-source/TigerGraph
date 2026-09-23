"""
Gather More Evidence Node — Issues a controlled evidence-request action (simulated).
Adds an EvidenceItem node and loops back to resolve_entities.
"""
import sys
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState
from schema.tg_connection import get_tg_connection


EVIDENCE_TYPES = [
    "device_history_check",
    "transaction_velocity_analysis",
    "address_verification",
    "email_pattern_analysis",
    "ring_expansion_search",
    "merchant_risk_assessment",
    "temporal_pattern_analysis",
]


def gather_more_evidence(state: AgentState) -> dict:
    """
    Simulate gathering additional evidence to refine hypotheses.
    Creates a new EvidenceItem and increments the loop counter.
    """
    case_id = state.get("case_id", "")
    evidence_loop_count = state.get("evidence_loop_count", 0)
    evidence_collected = list(state.get("evidence_collected", []))
    evidence_summaries = list(state.get("evidence_summaries", []))
    hypothesis_board = list(state.get("hypothesis_board", []))
    errors = list(state.get("errors", []))

    # Determine what type of evidence to gather based on current gaps
    evidence_type_idx = evidence_loop_count % len(EVIDENCE_TYPES)
    evidence_type = EVIDENCE_TYPES[evidence_type_idx]

    evidence_id = f"EV_{uuid.uuid4().hex[:10]}"
    summary_text = (
        f"Additional evidence gathered: {evidence_type.replace('_', ' ')} "
        f"(loop {evidence_loop_count + 1}). "
        f"Analysis indicates patterns consistent with ongoing investigation."
    )

    # Write to TigerGraph
    try:
        conn = get_tg_connection()
        conn.upsertVertex("EvidenceItem", evidence_id, attributes={
            "kind": evidence_type,
            "summary": summary_text,
            "collected_at": datetime.utcnow().isoformat(),
            "source": "automated_analysis",
        })

        # Link to case
        conn.upsertEdge("FraudCase", case_id,
                        "HAS_EVIDENCE", "EvidenceItem", evidence_id,
                        attributes={"added_at": datetime.utcnow().isoformat()})

        # Add SUPPORTS edge to leading hypothesis with slightly increased weight
        if hypothesis_board:
            leading = max(hypothesis_board, key=lambda h: h.get("confidence", 0))
            # Slightly boost leading hypothesis confidence with new evidence
            boost = 0.05 + (0.02 * evidence_loop_count)
            conn.upsertEdge("EvidenceItem", evidence_id,
                            "SUPPORTS", "TypologyPattern", leading["typology_id"],
                            attributes={"weight": boost})

            # Update confidence
            for h in hypothesis_board:
                if h["typology_id"] == leading["typology_id"]:
                    h["confidence"] = min(0.95, h["confidence"] + boost)
                    h["supporting_evidence_ids"].append(evidence_id)
                else:
                    # Slightly decay competing hypotheses
                    h["confidence"] = max(0.01, h["confidence"] - 0.02)

    except Exception as e:
        errors.append(f"Error gathering evidence: {e}")

    evidence_collected.append(evidence_id)
    evidence_summaries.append(summary_text)

    print(f"  [gather_more_evidence] Gathered {evidence_type} "
          f"(loop {evidence_loop_count + 1})")

    return {
        "evidence_collected": evidence_collected,
        "evidence_summaries": evidence_summaries,
        "evidence_loop_count": evidence_loop_count + 1,
        "hypothesis_board": hypothesis_board,
        "errors": errors,
        "stop_reason": None,  # Reset so assess_uncertainty re-evaluates
    }
