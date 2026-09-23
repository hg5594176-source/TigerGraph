"""
Schema creation and validation script.
Installs the full HHGOA_IEEE schema on TigerGraph and verifies it.
"""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from schema.tg_connection import get_tg_connection, verify_connection


SCHEMA_GSQL = """
// --- Vertex Types ---
CREATE VERTEX Client (PRIMARY_ID id STRING, first_seen DATETIME, risk_flags SET<STRING>)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX Card (PRIMARY_ID id STRING, card_type STRING, card_network STRING)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX Device (PRIMARY_ID id STRING, device_type STRING, device_info STRING)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX EmailDomain (PRIMARY_ID id STRING, domain STRING, is_free_provider BOOL)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX Transaction (PRIMARY_ID id STRING, amount DOUBLE, dt DATETIME,
    risk_score DOUBLE, product_code STRING)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX FraudCase (PRIMARY_ID id STRING, opened_at DATETIME,
    status STRING, trigger_type STRING)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX EvidenceItem (PRIMARY_ID id STRING, kind STRING, summary STRING,
    collected_at DATETIME, source STRING)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX TypologyPattern (PRIMARY_ID id STRING, name STRING,
    description STRING, documented BOOL)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX ActionType (PRIMARY_ID id STRING, name STRING, reversible BOOL)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX PolicyRule (PRIMARY_ID id STRING, text STRING, section STRING)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"
CREATE VERTEX Role (PRIMARY_ID id STRING, name STRING)
    WITH STATS="OUTDEGREE_BY_EDGETYPE"

// --- Edges ---
CREATE UNDIRECTED EDGE OWNS (FROM Client, TO Card)
CREATE UNDIRECTED EDGE USES_DEVICE (FROM Client, TO Device)
CREATE DIRECTED EDGE PAID_WITH (FROM Transaction, TO Card)
CREATE DIRECTED EDGE INITIATED_BY (FROM Transaction, TO Client)
CREATE DIRECTED EDGE FROM_DEVICE (FROM Transaction, TO Device)
CREATE DIRECTED EDGE TO_DOMAIN (FROM Transaction, TO EmailDomain)
CREATE DIRECTED EDGE INVESTIGATES (FROM FraudCase, TO Transaction)
CREATE DIRECTED EDGE ABOUT_CLIENT (FROM FraudCase, TO Client)
CREATE DIRECTED EDGE HAS_EVIDENCE (FROM FraudCase, TO EvidenceItem,
    added_at DATETIME)
CREATE DIRECTED EDGE SUPPORTS (FROM EvidenceItem, TO TypologyPattern,
    weight DOUBLE)
CREATE DIRECTED EDGE CONTRADICTS (FROM EvidenceItem, TO TypologyPattern,
    weight DOUBLE)
CREATE DIRECTED EDGE TOOK_ACTION (FROM FraudCase, TO ActionType,
    decided_at DATETIME, approved_by STRING)
CREATE DIRECTED EDGE APPLIES_TO (FROM PolicyRule, TO TypologyPattern)
CREATE DIRECTED EDGE REQUIRES_APPROVAL_FROM (FROM ActionType, TO Role)
CREATE UNDIRECTED EDGE SHARED_DEVICE (FROM Client, TO Client,
    ring_score DOUBLE, shared_device_id STRING)
CREATE UNDIRECTED EDGE SHARED_EMAIL (FROM Client, TO Client,
    ring_score DOUBLE, shared_domain STRING)
"""

CREATE_GRAPH = """
CREATE GRAPH HHGOA_IEEE (
    Client, Card, Device, EmailDomain, Transaction,
    FraudCase, EvidenceItem, TypologyPattern, ActionType, PolicyRule, Role,
    OWNS, USES_DEVICE, PAID_WITH, INITIATED_BY, FROM_DEVICE, TO_DOMAIN,
    INVESTIGATES, ABOUT_CLIENT, HAS_EVIDENCE, SUPPORTS, CONTRADICTS,
    TOOK_ACTION, APPLIES_TO, REQUIRES_APPROVAL_FROM, SHARED_DEVICE, SHARED_EMAIL
)
"""

EXPECTED_VERTEX_TYPES = {
    "Client", "Card", "Device", "EmailDomain", "Transaction",
    "FraudCase", "EvidenceItem", "TypologyPattern", "ActionType",
    "PolicyRule", "Role"
}

EXPECTED_EDGE_TYPES = {
    "OWNS", "USES_DEVICE", "PAID_WITH", "INITIATED_BY", "FROM_DEVICE",
    "TO_DOMAIN", "INVESTIGATES", "ABOUT_CLIENT", "HAS_EVIDENCE",
    "SUPPORTS", "CONTRADICTS", "TOOK_ACTION", "APPLIES_TO",
    "REQUIRES_APPROVAL_FROM", "SHARED_DEVICE", "SHARED_EMAIL"
}


def install_schema(conn):
    """Install the full schema on TigerGraph."""
    print("=" * 60)
    print("Installing HHGOA_IEEE Schema")
    print("=" * 60)

    # Execute schema DDL
    print("\n[1/3] Creating vertex and edge types...")
    try:
        result = conn.gsql(SCHEMA_GSQL)
        print(f"  Schema DDL result: {result}")
    except Exception as e:
        print(f"  Warning during schema creation: {e}")
        print("  (This may be OK if types already exist)")

    # Create graph
    print("\n[2/3] Creating graph HHGOA_IEEE...")
    try:
        result = conn.gsql(CREATE_GRAPH)
        print(f"  Graph creation result: {result}")
    except Exception as e:
        print(f"  Warning during graph creation: {e}")
        print("  (This may be OK if graph already exists)")

    # Verify
    print("\n[3/3] Verifying schema installation...")
    info = verify_connection(conn)

    if info["status"] == "error":
        print(f"  ERROR: {info['error']}")
        return False

    installed_vertices = set(info.get("vertex_types", []))
    installed_edges = set(info.get("edge_types", []))

    missing_vertices = EXPECTED_VERTEX_TYPES - installed_vertices
    missing_edges = EXPECTED_EDGE_TYPES - installed_edges

    print(f"\n  Vertex types: {len(installed_vertices)} installed")
    print(f"  Edge types: {len(installed_edges)} installed")

    if missing_vertices:
        print(f"\n  MISSING vertex types: {missing_vertices}")
    if missing_edges:
        print(f"\n  MISSING edge types: {missing_edges}")

    # Check vertex counts are 0
    print("\n  Vertex counts (should all be 0):")
    for vtype in sorted(installed_vertices & EXPECTED_VERTEX_TYPES):
        try:
            count = conn.getVertexCount(vtype)
            status = "✓" if count == 0 else f"⚠ (count={count})"
            print(f"    {vtype}: {count} {status}")
        except Exception as e:
            print(f"    {vtype}: ERROR ({e})")

    success = not missing_vertices and not missing_edges
    print(f"\n{'=' * 60}")
    print(f"Schema installation: {'SUCCESS ✓' if success else 'INCOMPLETE ✗'}")
    print(f"{'=' * 60}")
    return success


def main():
    print("Connecting to TigerGraph...")
    try:
        conn = get_tg_connection()
        print(f"  Connected to {conn.host}")
    except Exception as e:
        print(f"ERROR: Could not connect to TigerGraph: {e}")
        print("Please check your .env file and ensure TigerGraph is running.")
        sys.exit(1)

    success = install_schema(conn)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
