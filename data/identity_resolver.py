"""
Identity Resolution — ClientID Derivation from IEEE-CIS Transaction Data.

Reconstructs a stable pseudo-identity (ClientID) from card/address/timing
features since the dataset has no explicit customer key.

Composite key: (card1, card2, card3, card5, addr1, addr2, account_open_date)
where account_open_date = TransactionDT - D1 (rounded to the day).
"""
import sys
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda x, **kwargs: x

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import config

# Reference datetime for TransactionDT (IEEE-CIS starts at 2017-12-01)
REFERENCE_DATETIME = pd.Timestamp("2017-12-01")
EXPECTED_CLIENT_COUNT_LOW = 6_000
EXPECTED_CLIENT_COUNT_HIGH = 27_000
TARGET_CLIENT_COUNT = 13_500


def load_raw_data(raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load the raw transaction and identity CSVs."""
    txn_path = raw_dir / "train_transaction.csv"
    id_path = raw_dir / "train_identity.csv"

    if not txn_path.exists():
        raise FileNotFoundError(
            f"Transaction CSV not found at {txn_path}. "
            f"Please place IEEE-CIS train_transaction.csv in {raw_dir}"
        )

    print(f"Loading transactions from {txn_path}...")
    txn_df = pd.read_csv(txn_path)
    print(f"  → {len(txn_df):,} transactions loaded")

    id_df = None
    if id_path.exists():
        print(f"Loading identity data from {id_path}...")
        id_df = pd.read_csv(id_path)
        print(f"  → {len(id_df):,} identity records loaded")
    else:
        print(f"  Warning: Identity CSV not found at {id_path}")

    return txn_df, id_df


def derive_client_id(txn_df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive ClientID from composite key.

    Key components:
    - card1, card2, card3, card5 (card identifiers)
    - addr1, addr2 (address info)
    - account_open_date: TransactionDT - D1 (rounded to day)

    card4 (network) and card6 (type) are excluded as they're categorical
    descriptors, not identity signals.
    """
    print("\nDeriving ClientID from composite key...")

    df = txn_df.copy()

    # Convert TransactionDT (seconds offset) to datetime
    df["transaction_datetime"] = REFERENCE_DATETIME + pd.to_timedelta(df["TransactionDT"], unit="s")

    # Derive account open date: TransactionDT - D1 days, rounded to day
    # D1 is "timedelta" — typically days since account opening or first transaction
    df["D1_filled"] = df["D1"].fillna(0)
    df["account_open_date"] = (
        df["transaction_datetime"] - pd.to_timedelta(df["D1_filled"], unit="D")
    ).dt.date

    # Fill NaN in key columns with placeholder
    key_cols = ["card1", "card2", "card3", "card5", "addr1", "addr2"]
    for col in key_cols:
        df[col] = df[col].fillna(-999).astype(str)

    df["account_open_date_str"] = df["account_open_date"].astype(str)

    # Build composite key
    composite_parts = key_cols + ["account_open_date_str"]
    df["composite_key"] = df[composite_parts].agg("|".join, axis=1)

    # Hash to stable UID
    df["ClientID"] = df["composite_key"].apply(
        lambda x: "CLI_" + hashlib.md5(x.encode()).hexdigest()[:12]
    )

    n_clients = df["ClientID"].nunique()
    print(f"\n  Distinct ClientIDs: {n_clients:,}")
    print(f"  Expected range: {EXPECTED_CLIENT_COUNT_LOW:,} - {EXPECTED_CLIENT_COUNT_HIGH:,}")
    print(f"  Target: ~{TARGET_CLIENT_COUNT:,}")

    # Sanity check
    ratio = n_clients / TARGET_CLIENT_COUNT
    if ratio > 2.0 or ratio < 0.5:
        print(f"\n  [!] WARNING: Client count is {ratio:.1f}x the expected ~{TARGET_CLIENT_COUNT:,}")
        print("  The identity resolution key may be too strict (>2x) or too loose (<0.5x).")
        print("  Investigate before proceeding!")
        if ratio > 2.0:
            print("  Hint: key may be too strict. Consider dropping account_open_date from key.")
        else:
            print("  Hint: key may be too loose. Consider adding more card fields.")
    else:
        print(f"  [PASS] Client count is within expected range ({ratio:.2f}x target)")

    return df


def extract_entities(txn_df: pd.DataFrame, id_df: pd.DataFrame | None) -> dict[str, pd.DataFrame]:
    """Extract all entity tables for graph loading."""
    results = {}

    # --- Clients ---
    print("\nExtracting Client entities...")
    client_first_seen = txn_df.groupby("ClientID")["transaction_datetime"].min().reset_index()
    client_first_seen.columns = ["id", "first_seen"]
    client_first_seen["risk_flags"] = ""  # Will be populated by ring detection
    results["clients"] = client_first_seen
    print(f"  → {len(client_first_seen):,} clients")

    # --- Cards ---
    print("Extracting Card entities...")
    card_cols = ["card1", "card2", "card3", "card4", "card5", "card6"]
    available_card_cols = [c for c in card_cols if c in txn_df.columns]

    # Card ID from card1 (primary card identifier)
    cards = txn_df.drop_duplicates(subset=["card1"])[["card1"]].copy()
    cards["id"] = "CARD_" + cards["card1"].astype(str)
    cards["card_type"] = txn_df.drop_duplicates(subset=["card1"])["card6"].fillna("unknown").values if "card6" in txn_df.columns else "unknown"
    cards["card_network"] = txn_df.drop_duplicates(subset=["card1"])["card4"].fillna("unknown").values if "card4" in txn_df.columns else "unknown"
    results["cards"] = cards[["id", "card_type", "card_network"]]
    print(f"  → {len(cards):,} cards")

    # --- Devices ---
    print("Extracting Device entities...")
    if id_df is not None and "DeviceType" in id_df.columns:
        merged = txn_df.merge(id_df, on="TransactionID", how="left")
        devices = merged[merged["DeviceType"].notna()].drop_duplicates(
            subset=["DeviceType", "DeviceInfo"]
        )[["DeviceType", "DeviceInfo"]].copy()
        devices["DeviceInfo"] = devices["DeviceInfo"].fillna("unknown")
        devices["id"] = "DEV_" + devices.apply(
            lambda r: hashlib.md5(f"{r['DeviceType']}|{r['DeviceInfo']}".encode()).hexdigest()[:10],
            axis=1
        )
        devices.columns = ["device_type", "device_info", "id"]
        results["devices"] = devices[["id", "device_type", "device_info"]]
    elif id_df is not None and "id_30" in id_df.columns:
        # Alternative: use id_30 (OS version) and id_31 (browser) as device proxy
        merged = txn_df.merge(id_df, on="TransactionID", how="left")
        devices = merged[merged["id_30"].notna()].drop_duplicates(
            subset=["id_30", "id_31"]
        )[["id_30", "id_31"]].copy()
        devices["id_31"] = devices["id_31"].fillna("unknown")
        devices["id"] = "DEV_" + devices.apply(
            lambda r: hashlib.md5(f"{r['id_30']}|{r['id_31']}".encode()).hexdigest()[:10],
            axis=1
        )
        devices = devices.rename(columns={"id_30": "device_type", "id_31": "device_info"})
        results["devices"] = devices[["id", "device_type", "device_info"]]
    else:
        results["devices"] = pd.DataFrame(columns=["id", "device_type", "device_info"])
    print(f"  → {len(results['devices']):,} devices")

    # --- Email Domains ---
    print("Extracting EmailDomain entities...")
    FREE_PROVIDERS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
                      "aol.com", "protonmail.com", "mail.com", "yandex.com"}
    email_cols = [c for c in txn_df.columns if "email" in c.lower() or c.startswith("P_emaildomain") or c.startswith("R_emaildomain")]

    domains = set()
    for col in email_cols:
        if col in txn_df.columns:
            domains.update(txn_df[col].dropna().unique())

    domain_df = pd.DataFrame({"domain": list(domains)})
    domain_df["id"] = "EMAIL_" + domain_df["domain"].apply(
        lambda x: hashlib.md5(str(x).encode()).hexdigest()[:10]
    )
    domain_df["is_free_provider"] = domain_df["domain"].str.lower().isin(FREE_PROVIDERS)
    results["email_domains"] = domain_df[["id", "domain", "is_free_provider"]]
    print(f"  → {len(domain_df):,} email domains")

    # --- Transactions ---
    print("Extracting Transaction entities...")
    transactions = txn_df[["TransactionID", "TransactionAmt", "transaction_datetime",
                           "ClientID"]].copy()
    transactions.columns = ["id", "amount", "dt", "client_id"]
    transactions["id"] = "TXN_" + transactions["id"].astype(str)
    transactions["risk_score"] = 0.0  # Will be computed later
    transactions["product_code"] = txn_df["ProductCD"].fillna("unknown")
    results["transactions"] = transactions
    print(f"  → {len(transactions):,} transactions")

    # --- Edges: INITIATED_BY (Transaction → Client) ---
    print("Building edges...")
    initiated_by = transactions[["id", "client_id"]].copy()
    initiated_by.columns = ["transaction_id", "client_id"]
    results["edges_initiated_by"] = initiated_by

    # --- Edges: PAID_WITH (Transaction → Card) ---
    paid_with = pd.DataFrame({
        "transaction_id": "TXN_" + txn_df["TransactionID"].astype(str),
        "card_id": "CARD_" + txn_df["card1"].astype(str)
    })
    results["edges_paid_with"] = paid_with

    # --- Edges: OWNS (Client → Card) ---
    owns = txn_df[["ClientID", "card1"]].drop_duplicates()
    owns = pd.DataFrame({
        "client_id": owns["ClientID"],
        "card_id": "CARD_" + owns["card1"].astype(str)
    })
    results["edges_owns"] = owns

    # --- Edges: TO_DOMAIN ---
    if "P_emaildomain" in txn_df.columns:
        to_domain = txn_df[txn_df["P_emaildomain"].notna()][["TransactionID", "P_emaildomain"]].copy()
        to_domain["transaction_id"] = "TXN_" + to_domain["TransactionID"].astype(str)
        to_domain["domain_id"] = "EMAIL_" + to_domain["P_emaildomain"].apply(
            lambda x: hashlib.md5(str(x).encode()).hexdigest()[:10]
        )
        results["edges_to_domain"] = to_domain[["transaction_id", "domain_id"]]
    else:
        results["edges_to_domain"] = pd.DataFrame(columns=["transaction_id", "domain_id"])

    return results


def save_processed_data(entities: dict[str, pd.DataFrame], output_dir: Path):
    """Save all processed entity tables as CSVs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for name, df in entities.items():
        path = output_dir / f"{name}.csv"
        df.to_csv(path, index=False)
        print(f"  Saved {name}: {len(df):,} rows → {path}")


def main():
    raw_dir = config.data.raw_dir
    processed_dir = config.data.processed_dir

    print("=" * 60)
    print("Identity Resolution — ClientID Derivation")
    print("=" * 60)

    # Load raw data
    txn_df, id_df = load_raw_data(raw_dir)

    # Derive ClientID
    txn_df = derive_client_id(txn_df)

    # Extract entities
    entities = extract_entities(txn_df, id_df)

    # Save processed data
    print(f"\nSaving processed data to {processed_dir}...")
    save_processed_data(entities, processed_dir)

    print(f"\n{'=' * 60}")
    print("Identity Resolution Complete ✓")
    print(f"{'=' * 60}")

    # Summary
    print(f"\nSummary:")
    print(f"  Transactions: {len(entities['transactions']):,}")
    print(f"  Clients: {len(entities['clients']):,}")
    print(f"  Cards: {len(entities['cards']):,}")
    print(f"  Devices: {len(entities['devices']):,}")
    print(f"  Email Domains: {len(entities['email_domains']):,}")


if __name__ == "__main__":
    main()
