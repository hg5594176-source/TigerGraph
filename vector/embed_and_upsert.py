"""
Embed and Upsert — Generates embeddings for PolicyRule text and FraudCase narratives,
then upserts them into TigerGraph vector attributes.
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import config
from schema.tg_connection import get_tg_connection

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("ERROR: sentence-transformers not installed. Run: pip install sentence-transformers")
    sys.exit(1)


def get_embedding_model():
    """Load the sentence-transformer embedding model."""
    print(f"Loading embedding model: {config.embedding.model_name}...")
    model = SentenceTransformer(config.embedding.model_name)
    return model


def embed_policy_rules(conn, model):
    """Embed all PolicyRule text and upsert vectors."""
    print("\n[1/2] Embedding PolicyRule text...")

    # Fetch all PolicyRule vertices
    try:
        rules = conn.getVertices("PolicyRule")
    except Exception:
        rules = []

    if not rules:
        print("  No PolicyRule vertices found. Run load_policy.py first.")
        return

    texts = []
    ids = []
    for rule in rules:
        attrs = rule.get("attributes", rule)
        rule_id = rule.get("v_id", attrs.get("id", ""))
        text = attrs.get("text", "")
        section = attrs.get("section", "")
        full_text = f"[{section}] {text}"
        texts.append(full_text)
        ids.append(rule_id)

    print(f"  Embedding {len(texts)} policy rules...")
    embeddings = model.encode(texts, show_progress_bar=True)

    print("  Upserting vectors...")
    for rule_id, embedding in zip(ids, embeddings):
        try:
            conn.upsertVertex("PolicyRule", rule_id, attributes={
                "text_embedding": embedding.tolist()
            })
        except Exception as e:
            print(f"    Warning upserting {rule_id}: {e}")

    print(f"  → {len(ids)} PolicyRule embeddings upserted ✓")


def generate_case_narrative(case_data: dict) -> str:
    """Generate a one-paragraph narrative from case graph structure."""
    attrs = case_data.get("attributes", case_data)
    case_id = case_data.get("v_id", attrs.get("id", "unknown"))
    status = attrs.get("status", "unknown")
    trigger = attrs.get("trigger_type", "unknown")

    narrative = (
        f"Fraud case {case_id} was triggered by {trigger} and resulted in "
        f"status: {status}. "
    )

    return narrative


def embed_fraud_cases(conn, model):
    """Generate narrative embeddings for all closed FraudCase nodes."""
    print("\n[2/2] Embedding FraudCase narratives...")

    try:
        cases = conn.getVertices("FraudCase")
    except Exception:
        cases = []

    if not cases:
        print("  No FraudCase vertices found. Load cases first.")
        return

    # Filter to closed cases only
    closed = [c for c in cases if c.get("attributes", c).get("status") in
              ("confirmed_fraud", "cleared")]

    if not closed:
        print("  No closed cases found.")
        return

    narratives = []
    ids = []
    for case in closed:
        case_id = case.get("v_id", case.get("attributes", {}).get("id", ""))
        narrative = generate_case_narrative(case)
        narratives.append(narrative)
        ids.append(case_id)

    print(f"  Embedding {len(narratives)} case narratives...")
    embeddings = model.encode(narratives, show_progress_bar=True)

    print("  Upserting vectors...")
    for case_id, embedding in zip(ids, embeddings):
        try:
            conn.upsertVertex("FraudCase", case_id, attributes={
                "narrative_embedding": embedding.tolist()
            })
        except Exception as e:
            print(f"    Warning upserting {case_id}: {e}")

    print(f"  → {len(ids)} FraudCase embeddings upserted ✓")


def main():
    print("=" * 60)
    print("Embed and Upsert — Vector Memory Population")
    print("=" * 60)

    conn = get_tg_connection()
    model = get_embedding_model()

    embed_policy_rules(conn, model)
    embed_fraud_cases(conn, model)

    print(f"\n{'=' * 60}")
    print("Embedding Complete ✓")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
