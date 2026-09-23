"""
Resolve Entities Node — Pull client context and ring neighbors from TigerGraph.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState
from schema.tg_connection import get_tg_connection


def resolve_entities(state: AgentState) -> dict:
    """Pull client context and ring neighbors via installed GSQL queries."""
    client_id = state.get("client_id", "")
    errors = list(state.get("errors", []))

    if not client_id:
        errors.append("No client_id available for entity resolution")
        return {"errors": errors}

    conn = get_tg_connection()
    client_context = {}
    ring_neighbors = []

    # Get client context
    try:
        result = conn.runInstalledQuery("get_client_context",
                                         params={"client_id": client_id})
        if result:
            client_context = result[0] if isinstance(result, list) else result
        print(f"  [resolve_entities] Client context loaded for {client_id}")
    except Exception as e:
        errors.append(f"get_client_context failed: {e}")
        # Fallback: direct vertex lookup
        try:
            vertex = conn.getVerticesById("Client", client_id)
            if vertex:
                client_context = {"client": vertex[0]}
        except Exception:
            pass

    # Get ring neighbors (2-hop BFS)
    try:
        result = conn.runInstalledQuery("get_ring_neighbors",
                                         params={"client_id": client_id, "hops": 2})
        if result:
            for item in (result if isinstance(result, list) else [result]):
                if "ring_neighbors" in item:
                    ring_neighbors = item["ring_neighbors"]
        print(f"  [resolve_entities] Found {len(ring_neighbors)} ring neighbors")
    except Exception as e:
        errors.append(f"get_ring_neighbors failed: {e}")

    # Build evidence summary from context
    evidence_summaries = list(state.get("evidence_summaries", []))
    if client_context:
        txn_count = client_context.get("transaction_count", 0)
        txn_total = client_context.get("transaction_total", 0)
        cards = client_context.get("cards", [])
        devices = client_context.get("devices", [])
        prior_cases = client_context.get("prior_cases", [])

        summary = (
            f"Client {client_id}: {txn_count} transactions totaling ${txn_total:.2f}, "
            f"{len(cards)} cards, {len(devices)} devices, "
            f"{len(prior_cases)} prior cases, "
            f"{len(ring_neighbors)} ring neighbors"
        )
        if summary not in evidence_summaries:
            evidence_summaries.append(summary)

    return {
        "client_context": client_context,
        "ring_neighbors": ring_neighbors,
        "evidence_summaries": evidence_summaries,
        "errors": errors,
    }
