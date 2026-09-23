"""
Policy Check Node — Traverses policy graph for the leading hypothesis.
Determines allowed actions and required approvals.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState
from schema.tg_connection import get_tg_connection


def policy_check(state: AgentState) -> dict:
    """
    Query the policy graph for the leading typology hypothesis.
    Returns applicable policy rules and required approvals.
    """
    leading_typology = state.get("leading_typology")
    errors = list(state.get("errors", []))
    policy_rules_cited = []

    if not leading_typology:
        hypothesis_board = state.get("hypothesis_board", [])
        if hypothesis_board:
            leading = max(hypothesis_board, key=lambda h: h.get("confidence", 0))
            leading_typology = leading.get("typology_id")

    if not leading_typology:
        errors.append("No leading typology for policy check")
        return {"policy_rules_cited": [], "errors": errors}

    conn = get_tg_connection()

    try:
        result = conn.runInstalledQuery("get_policy_for_typology",
                                         params={"typology_id": leading_typology})
        if result:
            for item in (result if isinstance(result, list) else [result]):
                if "rules" in item:
                    policy_rules_cited = item["rules"]
                if "action_approvals" in item:
                    # Merge action approval info
                    for rule in policy_rules_cited:
                        rule["action_approvals"] = item.get("action_approvals", [])

        print(f"  [policy_check] Found {len(policy_rules_cited)} policy rules "
              f"for typology {leading_typology}")

    except Exception as e:
        errors.append(f"Policy query failed: {e}")
        # Fallback: use hardcoded policy mapping
        from data.load_policy import POLICY_RULES
        for rule in POLICY_RULES:
            if leading_typology in rule.get("applies_to", []):
                policy_rules_cited.append({
                    "rule_id": rule["id"],
                    "section": rule["section"],
                    "text": rule["text"],
                })

    # Also retrieve policy rules via vector search for enhanced context
    try:
        from vector.retrieval import retrieve_policy_rules
        hypothesis_board = state.get("hypothesis_board", [])
        if hypothesis_board:
            leading = max(hypothesis_board, key=lambda h: h.get("confidence", 0))
            query = f"fraud policy for {leading.get('typology_name', 'unknown')}"
            vector_rules = retrieve_policy_rules(conn, query, top_k=3)
            # Merge without duplicates
            existing_ids = {r.get("rule_id") for r in policy_rules_cited}
            for vr in vector_rules:
                if vr.get("v_id") and vr["v_id"] not in existing_ids:
                    policy_rules_cited.append({
                        "rule_id": vr["v_id"],
                        "text": vr.get("attributes", {}).get("text", ""),
                        "section": vr.get("attributes", {}).get("section", ""),
                    })
    except Exception:
        pass

    return {
        "policy_rules_cited": policy_rules_cited,
        "errors": errors,
    }
