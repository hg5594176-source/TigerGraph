"""
Hybrid Retrieval — Combines structural graph queries with vector similarity
for policy-text lookup and precedent-case retrieval.
"""
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import config
from schema.tg_connection import get_tg_connection

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


_model = None


def get_model():
    global _model
    if _model is None:
        if SentenceTransformer is None:
            raise ImportError("sentence-transformers required")
        _model = SentenceTransformer(config.embedding.model_name)
    return _model


def retrieve_policy_rules(conn, query_text: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve policy rules relevant to a query using vector similarity.
    Used during assess/decide steps.
    """
    model = get_model()
    query_embedding = model.encode([query_text])[0].tolist()

    try:
        # TigerVector similarity search
        results = conn.runInstalledQuery("search_top_k_similarity", params={
            "vertex_type": "PolicyRule",
            "embedding_attribute": "text_embedding",
            "query_vector": query_embedding,
            "k": top_k,
        })
        return results
    except Exception:
        # Fallback: brute-force cosine similarity via Python
        return _fallback_vector_search(conn, "PolicyRule", "text_embedding",
                                       query_embedding, top_k)


def retrieve_precedent_cases(conn, client_id: str, typology_id: str,
                             query_text: str, top_k: int = 5) -> list[dict]:
    """
    Hybrid retrieval: structural pre-filter + vector rerank.
    1. Run find_similar_closed_cases for structural matches
    2. Rerank using vector similarity on case narratives
    """
    # Step 1: Structural pre-filter
    structural_results = []
    try:
        result = conn.runInstalledQuery("find_similar_closed_cases", params={
            "client_id": client_id,
            "typology_id": typology_id,
            "k": top_k * 2,  # Get more candidates for reranking
        })
        if result and isinstance(result, list):
            for item in result:
                if "similar_cases" in item:
                    structural_results = item["similar_cases"]
    except Exception as e:
        print(f"  Structural search failed: {e}")

    if not structural_results:
        # Fall back to pure vector search
        return retrieve_case_by_vector(conn, query_text, top_k)

    # Step 2: Vector rerank
    model = get_model()
    query_embedding = model.encode([query_text])[0]

    # Fetch embeddings for structural candidates
    reranked = []
    for case in structural_results:
        case_id = case.get("case_id", "")
        try:
            vertex = conn.getVerticesById("FraudCase", case_id)
            if vertex:
                attrs = vertex[0].get("attributes", {})
                case_embedding = attrs.get("narrative_embedding", [])
                if case_embedding:
                    import numpy as np
                    sim = float(np.dot(query_embedding, case_embedding) /
                               (np.linalg.norm(query_embedding) * np.linalg.norm(case_embedding) + 1e-8))
                else:
                    sim = case.get("similarity_score", 0)
                reranked.append({**case, "vector_score": sim,
                                "combined_score": 0.5 * case.get("similarity_score", 0) + 0.5 * sim})
        except Exception:
            reranked.append({**case, "vector_score": 0,
                           "combined_score": case.get("similarity_score", 0)})

    reranked.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
    return reranked[:top_k]


def retrieve_case_by_vector(conn, query_text: str, top_k: int = 5) -> list[dict]:
    """Pure vector search for cases."""
    model = get_model()
    query_embedding = model.encode([query_text])[0].tolist()

    try:
        results = conn.runInstalledQuery("search_top_k_similarity", params={
            "vertex_type": "FraudCase",
            "embedding_attribute": "narrative_embedding",
            "query_vector": query_embedding,
            "k": top_k,
        })
        return results
    except Exception:
        return _fallback_vector_search(conn, "FraudCase", "narrative_embedding",
                                       query_embedding, top_k)


def _fallback_vector_search(conn, vertex_type: str, attr_name: str,
                            query_vector: list, top_k: int) -> list[dict]:
    """Brute-force cosine similarity fallback when TigerVector is unavailable."""
    import numpy as np

    try:
        vertices = conn.getVertices(vertex_type, limit=1000)
    except Exception:
        return []

    results = []
    q = np.array(query_vector)
    for v in vertices:
        attrs = v.get("attributes", {})
        embedding = attrs.get(attr_name, [])
        if embedding and len(embedding) == len(query_vector):
            e = np.array(embedding)
            sim = float(np.dot(q, e) / (np.linalg.norm(q) * np.linalg.norm(e) + 1e-8))
            results.append({
                "v_id": v.get("v_id", ""),
                "score": sim,
                "attributes": attrs,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]
