"""
Mock Actions — Stubbed API calls that log to action_log.json.
NEVER calls anything real.
"""
import json
import sys
from pathlib import Path
from datetime import datetime

ACTION_LOG_PATH = Path(__file__).resolve().parent.parent / "output" / "action_log.json"


def _log_action(action_name: str, params: dict, result: dict):
    """Append action to the log file."""
    ACTION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action_name,
        "params": params,
        "result": result,
    }

    # Append to JSON array
    existing = []
    if ACTION_LOG_PATH.exists():
        try:
            existing = json.loads(ACTION_LOG_PATH.read_text())
        except (json.JSONDecodeError, Exception):
            existing = []

    existing.append(log_entry)
    ACTION_LOG_PATH.write_text(json.dumps(existing, indent=2, default=str))


def execute_action(action_name: str, params: dict) -> dict:
    """
    Execute a mock action. All actions are simulated — they only log.

    Args:
        action_name: Name of the action to execute
        params: Action parameters (case_id, client_id, etc.)

    Returns:
        dict with execution result
    """
    handlers = {
        "freeze_account": _mock_freeze_account,
        "block_card": _mock_block_card,
        "send_customer_message": _mock_send_message,
        "request_stepup_auth": _mock_stepup_auth,
        "file_sar": _mock_file_sar,
        "flag_for_review": _mock_flag_review,
        "decline_transaction": _mock_decline_txn,
        "close_case": _mock_close_case,
    }

    handler = handlers.get(action_name, _mock_unknown)
    result = handler(params)

    _log_action(action_name, params, result)
    return result


def _mock_freeze_account(params: dict) -> dict:
    return {
        "status": "simulated",
        "message": f"Account for client {params.get('client_id', '?')} would be frozen",
        "reversible": True,
    }


def _mock_block_card(params: dict) -> dict:
    return {
        "status": "simulated",
        "message": f"Card for client {params.get('client_id', '?')} would be blocked",
        "reversible": True,
    }


def _mock_send_message(params: dict) -> dict:
    return {
        "status": "simulated",
        "message": f"Customer message would be sent to {params.get('client_id', '?')}",
        "channel": "email+sms",
    }


def _mock_stepup_auth(params: dict) -> dict:
    return {
        "status": "simulated",
        "message": f"Step-up auth requested for {params.get('client_id', '?')}",
        "method": "sms_otp",
    }


def _mock_file_sar(params: dict) -> dict:
    return {
        "status": "simulated",
        "message": f"SAR would be filed for case {params.get('case_id', '?')}",
        "filing_deadline": "30 days",
    }


def _mock_flag_review(params: dict) -> dict:
    return {
        "status": "simulated",
        "message": f"Case {params.get('case_id', '?')} flagged for analyst review",
        "priority": "high" if params.get("confidence", 0) > 0.7 else "medium",
    }


def _mock_decline_txn(params: dict) -> dict:
    return {
        "status": "simulated",
        "message": f"Transaction would be declined for case {params.get('case_id', '?')}",
    }


def _mock_close_case(params: dict) -> dict:
    return {
        "status": "simulated",
        "message": f"Case {params.get('case_id', '?')} would be closed",
    }


def _mock_unknown(params: dict) -> dict:
    return {
        "status": "error",
        "message": "Unknown action — no mock handler available",
    }
