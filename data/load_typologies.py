"""
Load the 5 documented fraud typologies, action types, and roles into TigerGraph.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from schema.tg_connection import get_tg_connection

TYPOLOGIES = [
    {
        "id": "TYP_CNP",
        "name": "Card-Not-Present Fraud",
        "description": "Unauthorized use of stolen card credentials in online/phone transactions where the physical card is not required. Characterized by unusual merchant categories, shipping address mismatches, and rapid successive transactions.",
        "documented": True,
    },
    {
        "id": "TYP_ATO",
        "name": "Account Takeover",
        "description": "Unauthorized access to a legitimate customer account, typically via credential theft, phishing, or social engineering. Indicators include device/IP changes, password resets followed by high-value transactions, and email address changes.",
        "documented": True,
    },
    {
        "id": "TYP_SYNTH",
        "name": "Synthetic Identity Fraud",
        "description": "Creation of fictitious identities using combinations of real and fabricated personal information. Often involves multiple accounts sharing partial identity elements (SSN fragments, addresses) with manufactured credit histories.",
        "documented": True,
    },
    {
        "id": "TYP_FRIENDLY",
        "name": "Friendly Fraud / Chargeback Abuse",
        "description": "Legitimate cardholders who make genuine purchases then dispute the charges claiming fraud, non-receipt, or dissatisfaction. Pattern shows repeated disputes from same customer across merchants with successful goods delivery.",
        "documented": True,
    },
    {
        "id": "TYP_BINTEST",
        "name": "Card Testing / BIN Attack",
        "description": "Automated testing of stolen or generated card numbers via small transactions to verify validity before larger fraudulent purchases. Characterized by many small-amount transactions in rapid succession, often at e-commerce merchants with weak validation.",
        "documented": True,
    },
]

ACTION_TYPES = [
    {"id": "ACT_FREEZE", "name": "freeze_account", "reversible": True},
    {"id": "ACT_BLOCK", "name": "block_card", "reversible": True},
    {"id": "ACT_MSG", "name": "send_customer_message", "reversible": False},
    {"id": "ACT_STEPUP", "name": "request_stepup_auth", "reversible": False},
    {"id": "ACT_SAR", "name": "file_sar", "reversible": False},
    {"id": "ACT_FLAG", "name": "flag_for_review", "reversible": True},
    {"id": "ACT_DECLINE", "name": "decline_transaction", "reversible": False},
    {"id": "ACT_CLOSE", "name": "close_case", "reversible": False},
]

ROLES = [
    {"id": "ROLE_ANALYST", "name": "analyst"},
    {"id": "ROLE_SR_ANALYST", "name": "senior_analyst"},
    {"id": "ROLE_FRAUD_MGR", "name": "fraud_manager"},
    {"id": "ROLE_COMPLIANCE", "name": "compliance_officer"},
]

# ActionType → required approval Role
APPROVAL_REQUIREMENTS = [
    ("ACT_FREEZE", "ROLE_SR_ANALYST"),
    ("ACT_BLOCK", "ROLE_SR_ANALYST"),
    ("ACT_SAR", "ROLE_COMPLIANCE"),
    ("ACT_DECLINE", "ROLE_FRAUD_MGR"),
    ("ACT_CLOSE", "ROLE_ANALYST"),
]


def load_typologies(conn):
    """Load all typology, action type, role vertices and approval edges."""
    print("\n[1/4] Loading TypologyPattern vertices...")
    for t in TYPOLOGIES:
        conn.upsertVertex("TypologyPattern", t["id"], attributes={
            "name": t["name"],
            "description": t["description"],
            "documented": t["documented"],
        })
    print(f"  → {len(TYPOLOGIES)} typologies loaded")

    print("\n[2/4] Loading ActionType vertices...")
    for a in ACTION_TYPES:
        conn.upsertVertex("ActionType", a["id"], attributes={
            "name": a["name"],
            "reversible": a["reversible"],
        })
    print(f"  → {len(ACTION_TYPES)} action types loaded")

    print("\n[3/4] Loading Role vertices...")
    for r in ROLES:
        conn.upsertVertex("Role", r["id"], attributes={
            "name": r["name"],
        })
    print(f"  → {len(ROLES)} roles loaded")

    print("\n[4/4] Loading REQUIRES_APPROVAL_FROM edges...")
    for action_id, role_id in APPROVAL_REQUIREMENTS:
        conn.upsertEdge("ActionType", action_id,
                        "REQUIRES_APPROVAL_FROM", "Role", role_id)
    print(f"  → {len(APPROVAL_REQUIREMENTS)} approval requirement edges loaded")


def main():
    print("=" * 60)
    print("Loading Typologies, Actions, and Roles")
    print("=" * 60)

    conn = get_tg_connection()
    load_typologies(conn)

    # Verify
    for vtype in ["TypologyPattern", "ActionType", "Role"]:
        count = conn.getVertexCount(vtype)
        print(f"  {vtype}: {count}")

    print("\nDone ✓")


if __name__ == "__main__":
    main()
