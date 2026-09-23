"""
Install all GSQL queries into TigerGraph and validate them.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema.tg_connection import get_tg_connection

QUERIES_DIR = Path(__file__).resolve().parent

QUERY_FILES = [
    "get_client_context.gsql",
    "get_ring_neighbors.gsql",
    "find_similar_closed_cases.gsql",
    "get_case_subgraph.gsql",
    "get_policy_for_typology.gsql",
]


def install_all_queries(conn):
    """Install all GSQL queries."""
    print("=" * 60)
    print("Installing GSQL Queries")
    print("=" * 60)

    for qfile in QUERY_FILES:
        path = QUERIES_DIR / qfile
        query_name = qfile.replace(".gsql", "")
        print(f"\n[{QUERY_FILES.index(qfile)+1}/{len(QUERY_FILES)}] Installing {query_name}...")

        if not path.exists():
            print(f"  ERROR: File not found: {path}")
            continue

        gsql_text = path.read_text(encoding="utf-8")

        try:
            # Drop existing query if any
            try:
                conn.gsql(f"USE GRAPH HHGOA_IEEE\nDROP QUERY {query_name}")
            except Exception:
                pass

            # Install query
            result = conn.gsql(f"USE GRAPH HHGOA_IEEE\n{gsql_text}\nINSTALL QUERY {query_name}")
            print(f"  Result: {result}")
            print(f"  ✓ {query_name} installed")
        except Exception as e:
            print(f"  ERROR installing {query_name}: {e}")


def verify_queries(conn):
    """Verify all queries are installed."""
    print("\n" + "=" * 60)
    print("Verifying Installed Queries")
    print("=" * 60)

    try:
        installed = conn.getInstalledQueries()
        for qfile in QUERY_FILES:
            query_name = qfile.replace(".gsql", "")
            status = "✓" if query_name in str(installed) else "✗ NOT FOUND"
            print(f"  {query_name}: {status}")
    except Exception as e:
        print(f"  Could not verify: {e}")


def main():
    conn = get_tg_connection()
    install_all_queries(conn)
    verify_queries(conn)
    print("\nDone ✓")


if __name__ == "__main__":
    main()
