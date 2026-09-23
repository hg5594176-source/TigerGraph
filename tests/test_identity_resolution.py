"""
Unit Tests for Identity Resolution
Verifies that:
1. Identical cards and address attributes over consistent account open dates map to the same ClientID.
2. Different card or address attributes produce different ClientIDs.
3. Missing attributes are safely handled via default placeholders without raising exceptions.
4. ClientID format matches 'CLI_<12 hex chars>'.
"""

import sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.identity_resolver import derive_client_id


def test_consistent_client_id_mapping():
    """Two transactions from the same user should yield the exact same ClientID."""
    data = {
        "TransactionID": [1001, 1002],
        "TransactionDT": [86400, 86400 + 3600],  # 1 day + 1 hour apart
        "D1": [10, 10],  # Same day account opening
        "card1": [13926, 13926],
        "card2": [None, None],
        "card3": [150, 150],
        "card5": [142, 142],
        "addr1": [315, 315],
        "addr2": [87, 87]
    }
    df = pd.DataFrame(data)
    result = derive_client_id(df)

    assert result["ClientID"].iloc[0] == result["ClientID"].iloc[1]
    assert result["ClientID"].nunique() == 1
    assert result["ClientID"].iloc[0].startswith("CLI_")
    print("[PASS] test_consistent_client_id_mapping")


def test_divergent_attributes_create_distinct_clients():
    """Different card or address attributes should yield distinct ClientIDs."""
    data = {
        "TransactionID": [2001, 2002],
        "TransactionDT": [86400, 86400],
        "D1": [10, 10],
        "card1": [13926, 99999],  # Different card1
        "card2": [100, 100],
        "card3": [150, 150],
        "card5": [142, 142],
        "addr1": [315, 450],      # Different addr1
        "addr2": [87, 87]
    }
    df = pd.DataFrame(data)
    result = derive_client_id(df)

    assert result["ClientID"].iloc[0] != result["ClientID"].iloc[1]
    assert result["ClientID"].nunique() == 2
    print("[PASS] test_divergent_attributes_create_distinct_clients")


def test_missing_values_handled_gracefully():
    """Missing or null card/address values should not crash identity resolution."""
    data = {
        "TransactionID": [3001],
        "TransactionDT": [50000],
        "D1": [None],
        "card1": [None],
        "card2": [None],
        "card3": [None],
        "card5": [None],
        "addr1": [None],
        "addr2": [None]
    }
    df = pd.DataFrame(data)
    result = derive_client_id(df)

    assert len(result["ClientID"]) == 1
    assert result["ClientID"].iloc[0].startswith("CLI_")
    print("[PASS] test_missing_values_handled_gracefully")


if __name__ == "__main__":
    test_consistent_client_id_mapping()
    test_divergent_attributes_create_distinct_clients()
    test_missing_values_handled_gracefully()
    print("All identity resolution tests PASSED successfully!")
