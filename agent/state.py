"""
LangGraph Agent State — TypedDict schema carrying data between nodes.
"""
from typing import TypedDict, Optional


class HypothesisEntry(TypedDict):
    typology_id: str
    typology_name: str
    confidence: float
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]


class ActionRecord(TypedDict):
    action_id: str
    action_name: str
    decided_at: str
    approved_by: str
    requires_approval: bool
    approval_role: str


class AgentState(TypedDict):
    """State carried between all LangGraph nodes."""
    # Core identifiers
    case_id: str
    client_id: str
    trigger_type: str          # "signal", "report", or "analyst"
    trigger_data: dict         # Raw trigger payload

    # Investigation context
    client_context: dict       # From get_client_context
    ring_neighbors: list[dict]
    precedent_cases: list[dict]

    # Hypothesis tracking
    hypothesis_board: list[HypothesisEntry]

    # Evidence tracking
    evidence_collected: list[str]     # EvidenceItem IDs
    evidence_loop_count: int
    evidence_summaries: list[str]     # Human-readable evidence descriptions

    # Decision state
    stop_reason: Optional[str]   # "confident", "escalate", "policy_mandate", None
    leading_typology: Optional[str]
    recommended_actions: list[ActionRecord]
    policy_rules_cited: list[dict]

    # Output
    narrative: str                    # Human-readable case summary
    answer_file: dict                 # Structured answer for submission

    # Metadata
    errors: list[str]
    status: str                       # "in_progress", "decided", "escalated", "closed"
