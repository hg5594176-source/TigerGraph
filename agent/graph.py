"""
LangGraph Agent — StateGraph wiring all 10 investigation nodes.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.graph import StateGraph, START, END

from agent.state import AgentState
from agent.nodes.intake import intake
from agent.nodes.resolve_entities import resolve_entities
from agent.nodes.retrieve_precedent import retrieve_precedent
from agent.nodes.hypothesize import hypothesize
from agent.nodes.assess_uncertainty import assess_uncertainty
from agent.nodes.gather_more_evidence import gather_more_evidence
from agent.nodes.policy_check import policy_check
from agent.nodes.decide_action import decide_action
from agent.nodes.explain import explain
from agent.nodes.update_memory import update_memory


def _route_after_assess(state: AgentState) -> str:
    """
    Conditional routing after assess_uncertainty:
    - If stop_reason is set → proceed to policy_check
    - If None → loop back to gather_more_evidence
    """
    if state.get("stop_reason") is not None:
        return "policy_check"
    else:
        return "gather_more_evidence"


def build_investigation_graph() -> StateGraph:
    """
    Build the LangGraph investigation state machine.

    Flow:
    START → intake → resolve_entities → retrieve_precedent → hypothesize
        → assess_uncertainty
            → [uncertain] gather_more_evidence → resolve_entities (loop)
            → [confident/escalate/mandate] policy_check → decide_action
                → explain → update_memory → END
    """
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("intake", intake)
    builder.add_node("resolve_entities", resolve_entities)
    builder.add_node("retrieve_precedent", retrieve_precedent)
    builder.add_node("hypothesize", hypothesize)
    builder.add_node("assess_uncertainty", assess_uncertainty)
    builder.add_node("gather_more_evidence", gather_more_evidence)
    builder.add_node("policy_check", policy_check)
    builder.add_node("decide_action", decide_action)
    builder.add_node("explain", explain)
    builder.add_node("update_memory", update_memory)

    # Linear edges
    builder.add_edge(START, "intake")
    builder.add_edge("intake", "resolve_entities")
    builder.add_edge("resolve_entities", "retrieve_precedent")
    builder.add_edge("retrieve_precedent", "hypothesize")
    builder.add_edge("hypothesize", "assess_uncertainty")

    # Conditional: assess → policy_check OR gather_more_evidence
    builder.add_conditional_edges(
        "assess_uncertainty",
        _route_after_assess,
        {
            "policy_check": "policy_check",
            "gather_more_evidence": "gather_more_evidence",
        }
    )

    # Evidence gathering loop
    builder.add_edge("gather_more_evidence", "resolve_entities")

    # Decision path
    builder.add_edge("policy_check", "decide_action")
    builder.add_edge("decide_action", "explain")
    builder.add_edge("explain", "update_memory")
    builder.add_edge("update_memory", END)

    return builder.compile()


def run_investigation(trigger_data: dict, trigger_type: str = "signal") -> dict:
    """
    Run a complete investigation for a given trigger.

    Args:
        trigger_data: dict with at least 'client_id' and optionally 'transaction_ids'
        trigger_type: "signal", "report", or "analyst"

    Returns:
        Final AgentState with narrative and answer_file
    """
    graph = build_investigation_graph()

    initial_state: AgentState = {
        "case_id": "",
        "client_id": trigger_data.get("client_id", ""),
        "trigger_type": trigger_type,
        "trigger_data": trigger_data,
        "client_context": {},
        "ring_neighbors": [],
        "precedent_cases": [],
        "hypothesis_board": [],
        "evidence_collected": [],
        "evidence_loop_count": 0,
        "evidence_summaries": [],
        "stop_reason": None,
        "leading_typology": None,
        "recommended_actions": [],
        "policy_rules_cited": [],
        "narrative": "",
        "answer_file": {},
        "errors": [],
        "status": "pending",
    }

    print("=" * 60)
    print(f"Starting Investigation — Client: {trigger_data.get('client_id', 'unknown')}")
    print(f"Trigger Type: {trigger_type}")
    print("=" * 60)

    result = graph.invoke(initial_state)

    print(f"\n{'=' * 60}")
    print(f"Investigation Complete — Case: {result.get('case_id', 'unknown')}")
    print(f"Status: {result.get('status', 'unknown')}")
    print(f"Stop Reason: {result.get('stop_reason', 'unknown')}")
    print(f"Evidence Loops: {result.get('evidence_loop_count', 0)}")
    print(f"Actions: {[a['action_name'] for a in result.get('recommended_actions', [])]}")
    print(f"{'=' * 60}")

    return result


# CLI entry point
if __name__ == "__main__":
    import json

    # Example: run against a test client
    test_trigger = {
        "client_id": "CLI_test123",
        "transaction_ids": ["TXN_12345"],
    }

    result = run_investigation(test_trigger, trigger_type="signal")

    # Print narrative
    print("\n" + result.get("narrative", "No narrative generated"))

    # Save answer file
    answer = result.get("answer_file", {})
    if answer:
        output_path = Path(__file__).resolve().parent.parent / "output" / f"{result['case_id']}.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(answer, f, indent=2, default=str)
        print(f"\nAnswer file saved to: {output_path}")
