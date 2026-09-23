"""
Retrieve Precedent Node — Structural + vector hybrid search for similar past cases.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from agent.state import AgentState
from schema.tg_connection import get_tg_connection


def retrieve_precedent(state: AgentState) -> dict:
    """
    Search for similar closed cases using hybrid retrieval:
    1. Structural match via find_similar_closed_cases
    2. Vector rerank via case narrative similarity
    """
    client_id = state.get("client_id", "")
    hypothesis_board = state.get("hypothesis_board", [])
    errors = list(state.get("errors", []))
    evidence_summaries = list(state.get("evidence_summaries", []))

    # Determine primary typology to search against
    if hypothesis_board:
        primary_typology = max(hypothesis_board, key=lambda h: h.get("confidence", 0))
        typology_id = primary_typology.get("typology_id", "TYP_CNP")
    else:
        typology_id = "TYP_CNP"  # Default

    conn = get_tg_connection()
    precedent_cases = []

    # Structural search
    try:
        result = conn.runInstalledQuery("find_similar_closed_cases", params={
            "client_id": client_id,
            "typology_id": typology_id,
            "k": 5,
        })
        if result:
            for item in (result if isinstance(result, list) else [result]):
                if "similar_cases" in item:
                    precedent_cases = item["similar_cases"]
        print(f"  [retrieve_precedent] Found {len(precedent_cases)} similar cases")
    except Exception as e:
        errors.append(f"find_similar_closed_cases failed: {e}")

    # Vector rerank (if retrieval module available)
    try:
        from vector.retrieval import retrieve_precedent_cases
        query_text = " ".join(evidence_summaries[-3:]) if evidence_summaries else f"fraud investigation for client {client_id}"
        vector_results = retrieve_precedent_cases(conn, client_id, typology_id, query_text, top_k=5)
        if vector_results:
            precedent_cases = vector_results
            print(f"  [retrieve_precedent] Vector-reranked to {len(precedent_cases)} cases")
    except Exception as e:
        pass  # Vector retrieval is optional enhancement

    # Add to evidence summaries
    if precedent_cases:
        fraud_count = sum(1 for c in precedent_cases if c.get("status") == "confirmed_fraud")
        cleared_count = sum(1 for c in precedent_cases if c.get("status") == "cleared")
        summary = f"Found {len(precedent_cases)} similar past cases: {fraud_count} confirmed fraud, {cleared_count} cleared"
        if summary not in evidence_summaries:
            evidence_summaries.append(summary)

    return {
        "precedent_cases": precedent_cases,
        "evidence_summaries": evidence_summaries,
        "errors": errors,
    }
