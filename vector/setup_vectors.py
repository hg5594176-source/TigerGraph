"""
Vector Memory Setup — Adds vector attributes to EvidenceItem, FraudCase, PolicyRule.
Configures embedding dimensions for TigerVector.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import config
from schema.tg_connection import get_tg_connection


def setup_vector_attributes(conn):
    """Add vector attributes to vertex types for TigerVector."""
    dim = config.embedding.dimension
    print(f"Setting up vector attributes (dimension={dim})...")

    vector_configs = [
        ("EvidenceItem", "embedding"),
        ("FraudCase", "narrative_embedding"),
        ("PolicyRule", "text_embedding"),
    ]

    for vertex_type, attr_name in vector_configs:
        print(f"\n  Adding {attr_name} to {vertex_type}...")
        try:
            gsql = f"""
            USE GRAPH HHGOA_IEEE
            ALTER VERTEX {vertex_type} ADD ATTRIBUTE ({attr_name} LIST<DOUBLE>)
            """
            result = conn.gsql(gsql)
            print(f"    Result: {result}")
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"    Attribute already exists, skipping")
            else:
                print(f"    Warning: {e}")

    # Create vector index for similarity search
    print("\n  Creating vector indices...")
    for vertex_type, attr_name in vector_configs:
        try:
            gsql = f"""
            USE GRAPH HHGOA_IEEE
            CREATE VECTOR INDEX {vertex_type}_{attr_name}_idx
            ON {vertex_type}({attr_name})
            USING HNSW (dimension={dim}, metric="cosine")
            """
            result = conn.gsql(gsql)
            print(f"    Index {vertex_type}_{attr_name}_idx: {result}")
        except Exception as e:
            print(f"    Warning creating index: {e}")


def main():
    print("=" * 60)
    print("Vector Memory Setup")
    print("=" * 60)

    conn = get_tg_connection()
    setup_vector_attributes(conn)

    print(f"\n{'=' * 60}")
    print("Vector Setup Complete ✓")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
