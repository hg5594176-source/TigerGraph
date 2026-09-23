"""
Load fraud policy document into TigerGraph as PolicyRule nodes
with APPLIES_TO edges mapping rules to fraud typologies.
"""
import sys
import hashlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema.tg_connection import get_tg_connection

# Bank Fraud Policy Document — chunked into individual rules
# Each rule has a section reference and maps to applicable typologies
POLICY_RULES = [
    {
        "id": "POL_001",
        "section": "3.1 - Transaction Monitoring Thresholds",
        "text": "Any single transaction exceeding $5,000 must trigger an automatic alert for review. Transactions above $10,000 require immediate senior analyst review before processing.",
        "applies_to": ["TYP_CNP", "TYP_ATO"],
        "immediate_action": False,
    },
    {
        "id": "POL_002",
        "section": "3.2 - Velocity Checks",
        "text": "More than 5 transactions from the same card within a 1-hour window, or more than 15 transactions within 24 hours, must be flagged for review. If the total amount exceeds $2,000 in that window, the card should be temporarily blocked pending review.",
        "applies_to": ["TYP_BINTEST", "TYP_CNP"],
        "immediate_action": False,
    },
    {
        "id": "POL_003",
        "section": "3.3 - Geographic Anomalies",
        "text": "Transactions originating from a geographic location more than 500 miles from the cardholder's registered address within 2 hours of a local transaction must be flagged. Impossible travel scenarios require immediate card block.",
        "applies_to": ["TYP_CNP", "TYP_ATO"],
        "immediate_action": True,
    },
    {
        "id": "POL_004",
        "section": "4.1 - Account Takeover Indicators",
        "text": "A combination of password reset, email change, and high-value transaction within 24 hours constitutes a high-probability ATO event. The account must be frozen pending customer verification via secondary channel.",
        "applies_to": ["TYP_ATO"],
        "immediate_action": True,
    },
    {
        "id": "POL_005",
        "section": "4.2 - Device Fingerprint Changes",
        "text": "When a customer's transaction originates from a previously unseen device AND the transaction pattern deviates from historical norms (amount > 3x average, new merchant category), flag for review within 4 hours.",
        "applies_to": ["TYP_ATO", "TYP_CNP"],
        "immediate_action": False,
    },
    {
        "id": "POL_006",
        "section": "5.1 - Synthetic Identity Detection",
        "text": "Accounts sharing 3 or more identity elements (SSN prefix, phone, address, email domain) with other accounts flagged for fraud within 90 days must be investigated as potential synthetic identity rings.",
        "applies_to": ["TYP_SYNTH"],
        "immediate_action": False,
    },
    {
        "id": "POL_007",
        "section": "5.2 - Ring Detection Response",
        "text": "When community detection identifies a cluster of 5+ accounts sharing devices or email domains with at least one confirmed fraud case, all accounts in the cluster must be flagged for review within 24 hours.",
        "applies_to": ["TYP_SYNTH", "TYP_CNP"],
        "immediate_action": False,
    },
    {
        "id": "POL_008",
        "section": "6.1 - Chargeback Pattern Analysis",
        "text": "Customers with more than 3 chargebacks in 6 months, or a chargeback rate exceeding 2% of transactions, must be flagged for friendly fraud review. Repeat offenders (>5 chargebacks in 12 months) require senior analyst case review.",
        "applies_to": ["TYP_FRIENDLY"],
        "immediate_action": False,
    },
    {
        "id": "POL_009",
        "section": "6.2 - Merchant-Side Friendly Fraud",
        "text": "When delivery confirmation exists and the customer disputes a charge as 'not received', cross-reference with carrier tracking data before proceeding with chargeback. If delivery is confirmed, escalate as potential friendly fraud.",
        "applies_to": ["TYP_FRIENDLY"],
        "immediate_action": False,
    },
    {
        "id": "POL_010",
        "section": "7.1 - Card Testing Detection",
        "text": "Patterns of sequential small-amount transactions ($0.01-$5.00) from the same BIN range across multiple merchants within minutes indicate card testing. Immediately block affected cards and alert the issuing bank.",
        "applies_to": ["TYP_BINTEST"],
        "immediate_action": True,
    },
    {
        "id": "POL_011",
        "section": "7.2 - BIN Attack Response",
        "text": "When automated card number generation is detected (sequential card numbers, consistent small amounts, high decline rates), block the BIN range for new transactions and file a SAR within 24 hours.",
        "applies_to": ["TYP_BINTEST"],
        "immediate_action": True,
    },
    {
        "id": "POL_012",
        "section": "8.1 - SAR Filing Requirements",
        "text": "A Suspicious Activity Report must be filed within 30 days for any confirmed fraud case involving aggregate amounts exceeding $5,000, any case involving potential money laundering indicators, or any case involving a ring of 3+ linked accounts.",
        "applies_to": ["TYP_CNP", "TYP_ATO", "TYP_SYNTH", "TYP_BINTEST"],
        "immediate_action": False,
    },
    {
        "id": "POL_013",
        "section": "8.2 - Escalation Matrix",
        "text": "Cases must be escalated based on severity: Level 1 (auto-resolved by system), Level 2 (analyst review within 24h), Level 3 (senior analyst within 4h), Level 4 (fraud manager + compliance within 1h). Cases involving amounts over $50,000 or organized rings are automatically Level 4.",
        "applies_to": ["TYP_CNP", "TYP_ATO", "TYP_SYNTH", "TYP_FRIENDLY", "TYP_BINTEST"],
        "immediate_action": False,
    },
    {
        "id": "POL_014",
        "section": "9.1 - Customer Communication",
        "text": "When an account is frozen or a card is blocked due to suspected fraud, the customer must be notified within 2 hours via their verified contact method. Communication must not reveal specific fraud indicators or investigation details.",
        "applies_to": ["TYP_CNP", "TYP_ATO"],
        "immediate_action": False,
    },
    {
        "id": "POL_015",
        "section": "9.2 - Account Recovery",
        "text": "After an ATO case is confirmed and resolved, the customer must complete full re-verification (identity verification + new credentials + device registration) before account access is restored.",
        "applies_to": ["TYP_ATO"],
        "immediate_action": False,
    },
]


def load_policy(conn):
    """Load policy rules and their typology mappings."""
    print("\n[1/2] Loading PolicyRule vertices...")
    for rule in POLICY_RULES:
        conn.upsertVertex("PolicyRule", rule["id"], attributes={
            "text": rule["text"],
            "section": rule["section"],
        })
    print(f"  → {len(POLICY_RULES)} policy rules loaded")

    print("\n[2/2] Loading APPLIES_TO edges...")
    edge_count = 0
    for rule in POLICY_RULES:
        for typology_id in rule["applies_to"]:
            conn.upsertEdge("PolicyRule", rule["id"],
                            "APPLIES_TO", "TypologyPattern", typology_id)
            edge_count += 1
    print(f"  → {edge_count} APPLIES_TO edges loaded")


def main():
    print("=" * 60)
    print("Loading Fraud Policy Rules")
    print("=" * 60)

    conn = get_tg_connection()
    load_policy(conn)

    count = conn.getVertexCount("PolicyRule")
    print(f"\n  PolicyRule count: {count}")
    print("\nDone ✓")


if __name__ == "__main__":
    main()
