"""
Update Memory Node — Writes final case state, re-embeds narrative,
and updates ring scores if new links were found.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState
from schema.tg_connection import get_tg_connection


def update_memory(state: AgentState) -> dict:
    """
    Final node: persist case results and update vector memory.
    """
    case_id = state.get("case_id", "")
    narrative = state.get("narrative", "")
    status = state.get("status", "decided")
    errors = list(state.get("errors", []))

    conn = get_tg_connection()

    # Update case status
    try:
        conn.upsertVertex("FraudCase", case_id, attributes={
            "status": status,
        })
        print(f"  [update_memory] Case {case_id} status → {status}")
    except Exception as e:
        errors.append(f"Failed to update case status: {e}")

    # Re-embed narrative for future similarity search
    try:
        from sentence_transformers import SentenceTransformer
        from config import config

        model = SentenceTransformer(config.embedding.model_name)
        embedding = model.encode([narrative])[0].tolist()

        conn.upsertVertex("FraudCase", case_id, attributes={
            "narrative_embedding": embedding,
        })
        print(f"  [update_memory] Narrative re-embedded ({len(embedding)} dims)")
    except ImportError:
        print("  [update_memory] sentence-transformers not available, skipping embedding")
    except Exception as e:
        errors.append(f"Failed to re-embed narrative: {e}")

    # Update ring scores if new shared links were found during investigation
    ring_neighbors = state.get("ring_neighbors", [])
    if ring_neighbors:
        client_id = state.get("client_id", "")
        try:
            # Add risk flag to client
            conn.upsertVertex("Client", client_id, attributes={
                "risk_flags": [f"investigated_{case_id}"],
            })
        except Exception:
            pass

    print(f"  [update_memory] Memory update complete for case {case_id}")

    return {
        "status": status,
        "errors": errors,
    }
