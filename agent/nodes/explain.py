"""
Explain Node — Narrates the case subgraph traversal into a human-readable summary.
Uses get_case_subgraph as the single source of truth.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState
from schema.tg_connection import get_tg_connection


def explain(state: AgentState) -> dict:
    """
    Generate a human-readable narrative from the case subgraph.
    This powers both the UI explanation panel and the answer file.
    """
    case_id = state.get("case_id", "")
    hypothesis_board = state.get("hypothesis_board", [])
    recommended_actions = state.get("recommended_actions", [])
    evidence_summaries = state.get("evidence_summaries", [])
    stop_reason = state.get("stop_reason", "")
    client_id = state.get("client_id", "")
    errors = list(state.get("errors", []))

    # Fetch case subgraph from TigerGraph (single source of truth)
    case_subgraph = {}
    try:
        conn = get_tg_connection()
        result = conn.runInstalledQuery("get_case_subgraph",
                                         params={"case_id": case_id})
        if result:
            case_subgraph = result[0] if isinstance(result, list) else result
    except Exception as e:
        errors.append(f"get_case_subgraph failed: {e}")

    # Build narrative
    leading = max(hypothesis_board, key=lambda h: h.get("confidence", 0)) if hypothesis_board else None

    narrative_parts = []

    # Header
    narrative_parts.append(f"## Fraud Investigation Report — Case {case_id}")
    narrative_parts.append(f"**Client:** {client_id}")
    narrative_parts.append(f"**Status:** {state.get('status', 'unknown')}")
    narrative_parts.append(f"**Stop Reason:** {stop_reason}")
    narrative_parts.append("")

    # Hypothesis summary
    narrative_parts.append("### Hypothesis Analysis")
    if hypothesis_board:
        sorted_hyps = sorted(hypothesis_board,
                             key=lambda h: h.get("confidence", 0), reverse=True)
        for i, h in enumerate(sorted_hyps):
            marker = "→ " if i == 0 else "  "
            narrative_parts.append(
                f"{marker}**{h['typology_name']}**: {h['confidence']:.1%} confidence"
            )
    narrative_parts.append("")

    # Evidence trail
    narrative_parts.append("### Evidence Trail")
    for i, summary in enumerate(evidence_summaries, 1):
        narrative_parts.append(f"{i}. {summary}")
    narrative_parts.append("")

    # Actions
    narrative_parts.append("### Actions Taken")
    for action in recommended_actions:
        approval = ("Auto-executed" if action.get("approved_by") == "system_auto"
                     else f"Pending approval from {action.get('approval_role', 'unknown')}")
        narrative_parts.append(f"- **{action['action_name']}**: {approval}")
    narrative_parts.append("")

    # Conclusion
    narrative_parts.append("### Conclusion")
    if leading:
        if leading["confidence"] >= 0.7:
            narrative_parts.append(
                f"Strong evidence supports **{leading['typology_name']}** "
                f"with {leading['confidence']:.1%} confidence."
            )
        elif leading["confidence"] >= 0.4:
            narrative_parts.append(
                f"Moderate evidence suggests **{leading['typology_name']}** "
                f"with {leading['confidence']:.1%} confidence. "
                f"Further investigation may be warranted."
            )
        else:
            narrative_parts.append(
                f"Insufficient evidence to conclusively determine fraud type. "
                f"Leading hypothesis: {leading['typology_name']} at "
                f"{leading['confidence']:.1%}. Case escalated for analyst review."
            )

    narrative = "\n".join(narrative_parts)

    # Build structured answer file
    answer_file = {
        "case_id": case_id,
        "client_id": client_id,
        "leading_typology": leading["typology_name"] if leading else None,
        "confidence": leading["confidence"] if leading else 0.0,
        "actions_taken": [
            {"action_type": a["action_name"], "requires_approval": a.get("requires_approval", False), "approved_by": a.get("approved_by", "")}
            for a in recommended_actions
        ],
        "investigation_record": {
            "evidence": evidence_summaries,
            "findings": [
                {
                    "typology": h["typology_name"],
                    "typology_id": h["typology_id"],
                    "confidence": h["confidence"],
                }
                for h in sorted(hypothesis_board,
                                key=lambda h: h["confidence"], reverse=True)
            ],
            "decisions": [
                {
                    "action": a["action_name"],
                    "approved_by": a.get("approved_by", ""),
                    "requires_approval": a.get("requires_approval", False),
                    "decided_at": a.get("decided_at", ""),
                }
                for a in recommended_actions
            ],
            "actions": [a["action_name"] for a in recommended_actions],
        },
        "case_subgraph": case_subgraph,
        "sar_required": _check_sar_required(leading, recommended_actions),
        "next_best_action": _get_next_best_action(leading, recommended_actions),
        "stop_reason": stop_reason,
        "narrative": narrative,
    }

    # Write narrative back to case in TigerGraph
    try:
        conn = get_tg_connection()
        conn.upsertVertex("FraudCase", case_id, attributes={
            "status": state.get("status", "decided"),
        })
    except Exception:
        pass

    print(f"  [explain] Generated narrative ({len(narrative)} chars)")

    return {
        "narrative": narrative,
        "answer_file": answer_file,
        "errors": errors,
    }


def _check_sar_required(leading: dict | None, actions: list) -> bool:
    """Check if a SAR is required based on policy rules."""
    if not leading:
        return False
    # SAR required for high-confidence fraud typologies (not friendly fraud)
    if leading.get("confidence", 0) >= 0.6 and leading.get("typology_id") != "TYP_FRIENDLY":
        return True
    # SAR required if file_sar action was taken
    return any(a.get("action_name") == "file_sar" for a in actions)


def _get_next_best_action(leading: dict | None, actions: list) -> str:
    """Determine the next best action based on current state."""
    if not leading:
        return "escalate_to_analyst"
    taken = {a.get("action_name") for a in actions}
    if "flag_for_review" not in taken:
        return "flag_for_review"
    if leading.get("confidence", 0) >= 0.7 and "freeze_account" not in taken:
        return "freeze_account"
    if "send_customer_message" not in taken:
        return "send_customer_message"
    return "close_case"
