"""
Unit Tests for Deterministic Permission Layer
Verifies that:
1. Low-risk actions (send message, request step-up, flag for review) are auto-executable.
2. High-risk actions (block card, freeze account, file SAR) require specific human approval roles.
3. Unknown actions are fail-safe (never auto-executable).
4. Returned permission dicts cannot mutate original configuration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from controls.permission_layer import check_permission, is_auto_executable, PERMISSIONS


def test_auto_executable_actions():
    """Verify standard low-risk notifications and step-up auth run automatically."""
    assert is_auto_executable("send_customer_message") is True
    assert is_auto_executable("request_stepup_auth") is True
    assert is_auto_executable("flag_for_review") is True
    print("[PASS] test_auto_executable_actions")


def test_approval_required_actions():
    """Verify sensitive account and regulatory actions enforce strict roles."""
    sar_perm = check_permission("file_sar")
    assert sar_perm["auto_executable"] is False
    assert sar_perm["requires_approval"] is True
    assert sar_perm["approval_role"] == "compliance_officer"

    freeze_perm = check_permission("freeze_account")
    assert freeze_perm["auto_executable"] is False
    assert freeze_perm["approval_role"] == "senior_analyst"

    block_perm = check_permission("block_card")
    assert block_perm["auto_executable"] is False
    assert block_perm["approval_role"] == "senior_analyst"
    print("[PASS] test_approval_required_actions")


def test_unknown_action_fail_safe():
    """Verify completely unknown or hallucinatory actions require human oversight."""
    perm = check_permission("unrestricted_auto_wire_transfer")
    assert perm["auto_executable"] is False
    assert perm["requires_approval"] is True
    assert perm["approval_role"] == "fraud_manager"
    print("[PASS] test_unknown_action_fail_safe")


def test_permission_dict_immutability():
    """Verify callers cannot tamper with global permissions dictionary by mutating returned object."""
    perm = check_permission("block_card")
    perm["auto_executable"] = True
    # Verify original in PERMISSIONS remains untouched
    assert PERMISSIONS["block_card"]["auto_executable"] is False
    print("[PASS] test_permission_dict_immutability")


if __name__ == "__main__":
    test_auto_executable_actions()
    test_approval_required_actions()
    test_unknown_action_fail_safe()
    test_permission_dict_immutability()
    print("All permission layer tests PASSED successfully!")
