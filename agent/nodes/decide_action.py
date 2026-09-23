"""
Decide Action Node — Recommends/executes actions within permissions.
Consults the DETERMINISTIC permission layer (not LLM).
"""
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState, ActionRecord
from schema.tg_connection import get_tg_connection
from controls.permission_layer import check_permission, get_recommended_actions
from controls.mock_actions import execute_action


def decide_action(state: AgentState) -> dict:
    """
    Determine and execute appropriate actions based on:
    - Leading hypothesis and confidence
    - Policy rules
    - Deterministic permission layer (NOT LLM judgment)
    """
    hypothesis_board = state.get("hypothesis_board", [])
    stop_reason = state.get("stop_reason", "confident")
    leading_typology = state.get("leading_typology")
    policy_rules_cited = state.get("policy_rules_cited", [])
    case_id = state.get("case_id", "")
    client_id = state.get("client_id", "")
    errors = list(state.get("errors", []))

    recommended_actions: list[ActionRecord] = []

    if not hypothesis_board:
        return {
            "recommended_actions": [],
            "status": "escalated",
            "errors": errors + ["No hypotheses to decide on"],
        }

    leading = max(hypothesis_board, key=lambda h: h.get("confidence", 0))

    # Get recommended actions for the typology and confidence level
    action_candidates = get_recommended_actions(
        typology_id=leading["typology_id"],
        confidence=leading["confidence"],
        stop_reason=stop_reason,
    )

    conn = get_tg_connection()

    for action_name in action_candidates:
        # Check permission via deterministic layer
        perm = check_permission(action_name)

        action_record: ActionRecord = {
            "action_id": perm["action_id"],
            "action_name": action_name,
            "decided_at": datetime.utcnow().isoformat(),
            "approved_by": "",
            "requires_approval": perm["requires_approval"],
            "approval_role": perm.get("approval_role", ""),
        }

        if perm["auto_executable"]:
            # Execute the mock action
            result = execute_action(action_name, {
                "case_id": case_id,
                "client_id": client_id,
                "typology": leading["typology_name"],
                "confidence": leading["confidence"],
            })
            action_record["approved_by"] = "system_auto"
            print(f"  [decide_action] Auto-executed: {action_name}")
        else:
            # Queue for approval
            action_record["approved_by"] = f"pending_{perm['approval_role']}"
            print(f"  [decide_action] Requires approval: {action_name} "
                  f"(needs {perm['approval_role']})")

        # Write TOOK_ACTION edge to TigerGraph
        try:
            conn.upsertEdge(
                "FraudCase", case_id,
                "TOOK_ACTION", "ActionType", perm["action_id"],
                attributes={
                    "decided_at": action_record["decided_at"],
                    "approved_by": action_record["approved_by"],
                }
            )
        except Exception as e:
            errors.append(f"Error writing TOOK_ACTION edge: {e}")

        recommended_actions.append(action_record)

    # Determine case status
    if stop_reason == "escalate":
        status = "escalated"
    elif stop_reason == "confident" or stop_reason == "policy_mandate":
        status = "decided"
    else:
        status = "decided"

    return {
        "recommended_actions": recommended_actions,
        "status": status,
        "errors": errors,
    }
