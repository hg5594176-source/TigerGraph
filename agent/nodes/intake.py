"""
Intake Node — Normalizes trigger into a new FraudCase node in TigerGraph.
"""
import sys
import uuid
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState
from schema.tg_connection import get_tg_connection


def intake(state: AgentState) -> dict:
    """
    Create a new FraudCase node from the trigger data.
    Normalizes different trigger types (signal/report/analyst) into a case.
    """
    trigger = state.get("trigger_data", {})
    trigger_type = state.get("trigger_type", "signal")

    # Generate case ID
    case_id = f"CASE_{uuid.uuid4().hex[:12]}"
    client_id = trigger.get("client_id", "")
    transaction_ids = trigger.get("transaction_ids", [])

    # Create FraudCase node in TigerGraph
    try:
        conn = get_tg_connection()
        conn.upsertVertex("FraudCase", case_id, attributes={
            "opened_at": datetime.utcnow().isoformat(),
            "status": "open",
            "trigger_type": trigger_type,
        })

        # Link to client
        if client_id:
            conn.upsertEdge("FraudCase", case_id,
                            "ABOUT_CLIENT", "Client", client_id)

        # Link to investigated transactions
        for txn_id in transaction_ids:
            conn.upsertEdge("FraudCase", case_id,
                            "INVESTIGATES", "Transaction", txn_id)

        print(f"  [intake] Created case {case_id} for client {client_id}")

    except Exception as e:
        return {
            "case_id": case_id,
            "client_id": client_id,
            "errors": [f"Failed to create case in TigerGraph: {e}"],
            "status": "in_progress",
            "hypothesis_board": [],
            "evidence_collected": [],
            "evidence_summaries": [],
            "evidence_loop_count": 0,
            "stop_reason": None,
            "recommended_actions": [],
            "policy_rules_cited": [],
            "narrative": "",
            "answer_file": {},
        }

    return {
        "case_id": case_id,
        "client_id": client_id,
        "status": "in_progress",
        "hypothesis_board": [],
        "evidence_collected": [],
        "evidence_summaries": [],
        "evidence_loop_count": 0,
        "stop_reason": None,
        "recommended_actions": [],
        "policy_rules_cited": [],
        "errors": [],
        "narrative": "",
        "answer_file": {},
    }
