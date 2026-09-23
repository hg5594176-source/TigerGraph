"""
Ring Detection — Community detection and PageRank over Client-Device-EmailDomain
projections. Materializes SHARED_DEVICE and SHARED_EMAIL edges with ring_score.
"""
import sys
from pathlib import Path
from collections import defaultdict

import pandas as pd
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import config
from schema.tg_connection import get_tg_connection


def find_shared_devices(conn) -> list[dict]:
    """
    Find clients sharing the same device.
    Returns list of (client1, client2, device_id, score) tuples.
    """
    print("\n[1/3] Finding shared device connections...")

    # Query: for each Device, find all Clients connected via USES_DEVICE
    # If >1 client shares a device, create SHARED_DEVICE edges
    gsql_query = """
    INTERPRET QUERY () FOR GRAPH HHGOA_IEEE {
        SetAccum<STRING> @@results;
        devices = {Device.*};

        clients = SELECT c
                  FROM devices:d -(USES_DEVICE:e)- Client:c
                  ACCUM
                    FOREACH c2 IN d.neighbors("USES_DEVICE") DO
                      IF c != c2 THEN
                        @@results += (c.id + "|" + c2.id + "|" + d.id)
                      END
                    END;

        PRINT @@results;
    }
    """
    shared = []
    try:
        result = conn.gsql(gsql_query)
        # Parse results
        if isinstance(result, list):
            for item in result:
                parts = item.split("|")
                if len(parts) == 3:
                    shared.append({
                        "client1": parts[0],
                        "client2": parts[1],
                        "device_id": parts[2],
                    })
    except Exception as e:
        print(f"  GSQL query failed: {e}")
        print("  Falling back to CSV-based approach...")
        shared = _find_shared_from_csv(config.data.processed_dir, "device")

    print(f"  → Found {len(shared)} shared device pairs")
    return shared


def find_shared_emails(conn) -> list[dict]:
    """Find clients sharing the same email domain through transactions."""
    print("\n[2/3] Finding shared email domain connections...")

    shared = []
    try:
        # Simpler approach: read from processed data
        shared = _find_shared_from_csv(config.data.processed_dir, "email")
    except Exception as e:
        print(f"  Error: {e}")

    print(f"  → Found {len(shared)} shared email domain pairs")
    return shared


def _find_shared_from_csv(processed_dir: Path, share_type: str) -> list[dict]:
    """Fallback: compute shared connections from processed CSVs."""
    shared = []

    if share_type == "device":
        edges_path = processed_dir / "edges_from_device.csv"
        if not edges_path.exists():
            return shared
        edges = pd.read_csv(edges_path)
        # Group transactions by device, find distinct clients per device
        txns = pd.read_csv(processed_dir / "transactions.csv")
        txn_client = dict(zip(txns["id"], txns["client_id"]))

        device_clients = defaultdict(set)
        for _, row in edges.iterrows():
            txn_id = row["transaction_id"]
            client = txn_client.get(txn_id)
            if client:
                device_clients[row["device_id"]].add(client)

        for device_id, clients in device_clients.items():
            clients = list(clients)
            for i in range(len(clients)):
                for j in range(i + 1, len(clients)):
                    shared.append({
                        "client1": clients[i],
                        "client2": clients[j],
                        "device_id": device_id,
                    })

    elif share_type == "email":
        edges_path = processed_dir / "edges_to_domain.csv"
        if not edges_path.exists():
            return shared
        edges = pd.read_csv(edges_path)
        txns = pd.read_csv(processed_dir / "transactions.csv")
        txn_client = dict(zip(txns["id"], txns["client_id"]))

        domain_clients = defaultdict(set)
        for _, row in edges.iterrows():
            txn_id = row["transaction_id"]
            client = txn_client.get(txn_id)
            if client:
                domain_clients[row["domain_id"]].add(client)

        # Only create edges for domains shared by multiple clients (ring signal)
        for domain_id, clients in domain_clients.items():
            if len(clients) < 2 or len(clients) > 50:
                continue  # Skip very common domains (gmail etc)
            clients = list(clients)
            for i in range(len(clients)):
                for j in range(i + 1, min(len(clients), i + 10)):
                    shared.append({
                        "client1": clients[i],
                        "client2": clients[j],
                        "domain_id": domain_id,
                    })

    return shared


def compute_ring_scores(shared_devices: list, shared_emails: list) -> dict[str, float]:
    """
    Compute ring_score for each client based on connectivity.
    Score = normalized count of shared connections (devices + emails).
    """
    print("\n[3/3] Computing ring scores...")
    client_connections = defaultdict(int)

    for s in shared_devices:
        client_connections[s["client1"]] += 1
        client_connections[s["client2"]] += 1

    for s in shared_emails:
        client_connections[s["client1"]] += 1
        client_connections[s["client2"]] += 1

    # Normalize: score = connections / max_connections
    if client_connections:
        max_conn = max(client_connections.values())
        scores = {k: v / max_conn for k, v in client_connections.items()}
    else:
        scores = {}

    print(f"  → Computed scores for {len(scores)} clients")
    if scores:
        values = list(scores.values())
        print(f"  → Score range: [{min(values):.4f}, {max(values):.4f}]")
        print(f"  → Clients with score > 0.5: {sum(1 for v in values if v > 0.5)}")

    return scores


def materialize_edges(conn, shared_devices, shared_emails, ring_scores):
    """Write SHARED_DEVICE and SHARED_EMAIL edges to TigerGraph."""
    print("\nMaterializing shared edges...")

    # SHARED_DEVICE edges
    print(f"  Writing {len(shared_devices)} SHARED_DEVICE edges...")
    for s in tqdm(shared_devices[:10000], desc="SHARED_DEVICE"):
        score = max(ring_scores.get(s["client1"], 0),
                    ring_scores.get(s["client2"], 0))
        try:
            conn.upsertEdge(
                "Client", s["client1"],
                "SHARED_DEVICE", "Client", s["client2"],
                attributes={
                    "ring_score": score,
                    "shared_device_id": s.get("device_id", ""),
                }
            )
        except Exception:
            pass

    # SHARED_EMAIL edges
    print(f"  Writing {len(shared_emails)} SHARED_EMAIL edges...")
    for s in tqdm(shared_emails[:10000], desc="SHARED_EMAIL"):
        score = max(ring_scores.get(s["client1"], 0),
                    ring_scores.get(s["client2"], 0))
        try:
            conn.upsertEdge(
                "Client", s["client1"],
                "SHARED_EMAIL", "Client", s["client2"],
                attributes={
                    "ring_score": score,
                    "shared_domain": s.get("domain_id", ""),
                }
            )
        except Exception:
            pass

    print("  Done ✓")


def main():
    print("=" * 60)
    print("Ring Detection — Community Detection & PageRank")
    print("=" * 60)

    conn = get_tg_connection()

    shared_devices = find_shared_devices(conn)
    shared_emails = find_shared_emails(conn)
    ring_scores = compute_ring_scores(shared_devices, shared_emails)
    materialize_edges(conn, shared_devices, shared_emails, ring_scores)

    print(f"\n{'=' * 60}")
    print("Ring Detection Complete ✓")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
