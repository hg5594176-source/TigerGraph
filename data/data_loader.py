"""
Data Loader — Loads processed CSVs into TigerGraph via pyTigerGraph.
Handles all vertex and edge types with batch upserts.
"""
import sys
import json
from pathlib import Path

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import config
from schema.tg_connection import get_tg_connection


def load_vertices(conn, processed_dir: Path):
    """Load all vertex types from processed CSVs."""

    # --- Clients ---
    print("\n[1/5] Loading Client vertices...")
    clients = pd.read_csv(processed_dir / "clients.csv")
    for _, row in tqdm(clients.iterrows(), total=len(clients), desc="Clients"):
        conn.upsertVertex("Client", row["id"], attributes={
            "first_seen": str(row.get("first_seen", "")),
            "risk_flags": []
        })
    print(f"  → Upserted {len(clients):,} Client vertices")

    # --- Cards ---
    print("\n[2/5] Loading Card vertices...")
    cards = pd.read_csv(processed_dir / "cards.csv")
    for _, row in tqdm(cards.iterrows(), total=len(cards), desc="Cards"):
        conn.upsertVertex("Card", row["id"], attributes={
            "card_type": str(row.get("card_type", "unknown")),
            "card_network": str(row.get("card_network", "unknown"))
        })
    print(f"  → Upserted {len(cards):,} Card vertices")

    # --- Devices ---
    print("\n[3/5] Loading Device vertices...")
    devices_path = processed_dir / "devices.csv"
    if devices_path.exists():
        devices = pd.read_csv(devices_path)
        for _, row in tqdm(devices.iterrows(), total=len(devices), desc="Devices"):
            conn.upsertVertex("Device", row["id"], attributes={
                "device_type": str(row.get("device_type", "unknown")),
                "device_info": str(row.get("device_info", "unknown"))
            })
        print(f"  → Upserted {len(devices):,} Device vertices")
    else:
        print("  → No devices.csv found, skipping")

    # --- EmailDomains ---
    print("\n[4/5] Loading EmailDomain vertices...")
    domains = pd.read_csv(processed_dir / "email_domains.csv")
    for _, row in tqdm(domains.iterrows(), total=len(domains), desc="EmailDomains"):
        conn.upsertVertex("EmailDomain", row["id"], attributes={
            "domain": str(row.get("domain", "")),
            "is_free_provider": bool(row.get("is_free_provider", False))
        })
    print(f"  → Upserted {len(domains):,} EmailDomain vertices")

    # --- Transactions ---
    print("\n[5/5] Loading Transaction vertices...")
    txns = pd.read_csv(processed_dir / "transactions.csv")
    batch_size = 500
    for i in tqdm(range(0, len(txns), batch_size), desc="Transactions"):
        batch = txns.iloc[i:i + batch_size]
        vertices = []
        for _, row in batch.iterrows():
            vertices.append((
                row["id"],
                {
                    "amount": float(row.get("amount", 0)),
                    "dt": str(row.get("dt", "")),
                    "risk_score": float(row.get("risk_score", 0)),
                    "product_code": str(row.get("product_code", "unknown"))
                }
            ))
        for vid, attrs in vertices:
            conn.upsertVertex("Transaction", vid, attributes=attrs)
    print(f"  → Upserted {len(txns):,} Transaction vertices")


def load_edges(conn, processed_dir: Path):
    """Load all edge types from processed CSVs."""

    # --- INITIATED_BY ---
    print("\n[Edge 1/4] Loading INITIATED_BY edges...")
    edges_path = processed_dir / "edges_initiated_by.csv"
    if edges_path.exists():
        edges = pd.read_csv(edges_path)
        batch_size = 500
        for i in tqdm(range(0, len(edges), batch_size), desc="INITIATED_BY"):
            batch = edges.iloc[i:i + batch_size]
            for _, row in batch.iterrows():
                conn.upsertEdge("Transaction", row["transaction_id"],
                                "INITIATED_BY", "Client", row["client_id"])
        print(f"  → Upserted {len(edges):,} INITIATED_BY edges")

    # --- PAID_WITH ---
    print("\n[Edge 2/4] Loading PAID_WITH edges...")
    edges_path = processed_dir / "edges_paid_with.csv"
    if edges_path.exists():
        edges = pd.read_csv(edges_path)
        batch_size = 500
        for i in tqdm(range(0, len(edges), batch_size), desc="PAID_WITH"):
            batch = edges.iloc[i:i + batch_size]
            for _, row in batch.iterrows():
                conn.upsertEdge("Transaction", row["transaction_id"],
                                "PAID_WITH", "Card", row["card_id"])
        print(f"  → Upserted {len(edges):,} PAID_WITH edges")

    # --- OWNS ---
    print("\n[Edge 3/4] Loading OWNS edges...")
    edges_path = processed_dir / "edges_owns.csv"
    if edges_path.exists():
        edges = pd.read_csv(edges_path)
        for _, row in tqdm(edges.iterrows(), total=len(edges), desc="OWNS"):
            conn.upsertEdge("Client", row["client_id"],
                            "OWNS", "Card", row["card_id"])
        print(f"  → Upserted {len(edges):,} OWNS edges")

    # --- TO_DOMAIN ---
    print("\n[Edge 4/4] Loading TO_DOMAIN edges...")
    edges_path = processed_dir / "edges_to_domain.csv"
    if edges_path.exists():
        edges = pd.read_csv(edges_path)
        batch_size = 500
        for i in tqdm(range(0, len(edges), batch_size), desc="TO_DOMAIN"):
            batch = edges.iloc[i:i + batch_size]
            for _, row in batch.iterrows():
                conn.upsertEdge("Transaction", row["transaction_id"],
                                "TO_DOMAIN", "EmailDomain", row["domain_id"])
        print(f"  → Upserted {len(edges):,} TO_DOMAIN edges")


def verify_counts(conn):
    """Verify vertex counts after loading."""
    print("\n" + "=" * 60)
    print("Verification — Vertex Counts")
    print("=" * 60)
    for vtype in ["Client", "Card", "Device", "EmailDomain", "Transaction",
                   "FraudCase", "EvidenceItem", "TypologyPattern", "ActionType",
                   "PolicyRule", "Role"]:
        try:
            count = conn.getVertexCount(vtype)
            print(f"  {vtype}: {count:,}")
        except Exception as e:
            print(f"  {vtype}: ERROR ({e})")


def main():
    processed_dir = config.data.processed_dir

    if not processed_dir.exists():
        print(f"ERROR: Processed data directory not found: {processed_dir}")
        print("Run identity_resolver.py first.")
        sys.exit(1)

    print("=" * 60)
    print("Data Loader — Loading into TigerGraph")
    print("=" * 60)

    conn = get_tg_connection()
    print(f"Connected to {conn.host}")

    load_vertices(conn, processed_dir)
    load_edges(conn, processed_dir)
    verify_counts(conn)

    print(f"\n{'=' * 60}")
    print("Data Loading Complete ✓")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
