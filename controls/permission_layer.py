"""
Permission Layer — DETERMINISTIC policy enforcement.
Maps ActionType → auto_executable or requires_approval(role).

The LLM proposes actions; this layer DISPOSES.
No LLM can override these permissions, regardless of prompt content.
"""

# Deterministic permission mapping — Python dict, NOT an LLM instruction
PERMISSIONS = {
    "freeze_account": {
        "action_id": "ACT_FREEZE",
        "auto_executable": False,
        "requires_approval": True,
        "approval_role": "senior_analyst",
        "description": "Freeze customer account — requires senior analyst approval",
    },
    "block_card": {
        "action_id": "ACT_BLOCK",
        "auto_executable": False,
        "requires_approval": True,
        "approval_role": "senior_analyst",
        "description": "Block card — requires senior analyst approval",
    },
    "send_customer_message": {
        "action_id": "ACT_MSG",
        "auto_executable": True,
        "requires_approval": False,
        "approval_role": None,
        "description": "Send notification to customer — auto-executable",
    },
    "request_stepup_auth": {
        "action_id": "ACT_STEPUP",
        "auto_executable": True,
        "requires_approval": False,
        "approval_role": None,
        "description": "Request step-up authentication — auto-executable",
    },
    "file_sar": {
        "action_id": "ACT_SAR",
        "auto_executable": False,
        "requires_approval": True,
        "approval_role": "compliance_officer",
        "description": "File SAR — requires compliance officer approval",
    },
    "flag_for_review": {
        "action_id": "ACT_FLAG",
        "auto_executable": True,
        "requires_approval": False,
        "approval_role": None,
        "description": "Flag for analyst review — auto-executable",
    },
    "decline_transaction": {
        "action_id": "ACT_DECLINE",
        "auto_executable": False,
        "requires_approval": True,
        "approval_role": "fraud_manager",
        "description": "Decline transaction — requires fraud manager approval",
    },
    "close_case": {
        "action_id": "ACT_CLOSE",
        "auto_executable": False,
        "requires_approval": True,
        "approval_role": "analyst",
        "description": "Close case — requires analyst approval",
    },
}


def check_permission(action_name: str) -> dict:
    """
    Check if an action is permitted and what approval is needed.
    This is a PURE LOOKUP — no LLM involvement, no prompt interpretation.

    Returns:
        dict with keys: action_id, auto_executable, requires_approval, approval_role
    """
    if action_name not in PERMISSIONS:
        # Unknown actions are NEVER auto-executable
        return {
            "action_id": "UNKNOWN",
            "auto_executable": False,
            "requires_approval": True,
            "approval_role": "fraud_manager",
            "description": f"Unknown action '{action_name}' — requires fraud manager review",
        }

    # Return a COPY to prevent mutation
    return dict(PERMISSIONS[action_name])


def is_auto_executable(action_name: str) -> bool:
    """Simple boolean check: can this action be auto-executed?"""
    perm = check_permission(action_name)
    return perm["auto_executable"]


def get_recommended_actions(typology_id: str, confidence: float,
                            stop_reason: str) -> list[str]:
    """
    Determine recommended actions based on typology and confidence.
    This is deterministic logic — NOT an LLM judgment.
    """
    actions = []

    # Always flag for review
    actions.append("flag_for_review")

    # High confidence fraud
    if confidence >= 0.7:
        if typology_id in ("TYP_CNP", "TYP_BINTEST"):
            actions.append("block_card")
            actions.append("send_customer_message")
        elif typology_id == "TYP_ATO":
            actions.append("freeze_account")
            actions.append("send_customer_message")
            actions.append("request_stepup_auth")
        elif typology_id == "TYP_SYNTH":
            actions.append("freeze_account")
            actions.append("file_sar")
        elif typology_id == "TYP_FRIENDLY":
            actions.append("send_customer_message")

    # Moderate confidence
    elif confidence >= 0.4:
        actions.append("request_stepup_auth")
        actions.append("send_customer_message")

    # Policy mandate — immediate action regardless
    if stop_reason == "policy_mandate":
        if typology_id in ("TYP_ATO",):
            if "freeze_account" not in actions:
                actions.append("freeze_account")
        if typology_id in ("TYP_BINTEST",):
            if "block_card" not in actions:
                actions.append("block_card")

    # Escalation
    if stop_reason == "escalate":
        actions = ["flag_for_review"]  # Only flag, don't take drastic action

    # SAR filing for high-confidence non-friendly fraud
    if confidence >= 0.6 and typology_id != "TYP_FRIENDLY":
        if "file_sar" not in actions:
            actions.append("file_sar")

    return actions
