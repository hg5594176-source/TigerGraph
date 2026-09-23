"""
TigerGraph connection utility.
Provides a shared pyTigerGraph connection with automatic mock fallback
when credentials are not yet configured in .env.
"""

import sys
from typing import Any, Dict, List, Optional
from config import config, validate_config

try:
    import pyTigerGraph as tg
except ImportError:
    tg = None


class MockTigerGraphConnection:
    """In-memory mock TigerGraph connection for local development and offline testing."""

    def __init__(self, host: str = "mock-savanna.tgcloud.io", graphname: str = "HHGOA_IEEE"):
        self.host = host
        self.graphname = graphname
        self._vertices: Dict[str, Dict[str, Any]] = {}
        self._edges: List[Dict[str, Any]] = []

    def getVersion(self) -> str:
        return "TigerGraph Savanna 4.1 (Simulated/Fallback)"

    def getSchema(self) -> dict:
        return {
            "VertexTypes": [
                {"Name": "Client"}, {"Name": "Card"}, {"Name": "Device"},
                {"Name": "EmailDomain"}, {"Name": "Transaction"}, {"Name": "FraudCase"},
                {"Name": "EvidenceItem"}, {"Name": "TypologyPattern"}, {"Name": "ActionType"},
                {"Name": "PolicyRule"}, {"Name": "Role"}
            ],
            "EdgeTypes": [
                {"Name": "OWNS"}, {"Name": "USES_DEVICE"}, {"Name": "PAID_WITH"},
                {"Name": "INITIATED_BY"}, {"Name": "FROM_DEVICE"}, {"Name": "TO_DOMAIN"},
                {"Name": "INVESTIGATES"}, {"Name": "ABOUT_CLIENT"}, {"Name": "HAS_EVIDENCE"},
                {"Name": "SUPPORTS"}, {"Name": "CONTRADICTS"}, {"Name": "TOOK_ACTION"},
                {"Name": "APPLIES_TO"}, {"Name": "REQUIRES_APPROVAL_FROM"},
                {"Name": "SHARED_DEVICE"}, {"Name": "SHARED_EMAIL"}
            ]
        }

    def runInstalledQuery(self, query_name: str, params: Optional[dict] = None) -> list:
        params = params or {}
        client_id = params.get("client_id", "CLI-DEFAULT")
        case_id = params.get("case_id", "CASE-DEFAULT")

        if query_name == "get_client_context":
            return [{
                "client_id": client_id,
                "transaction_count": 8,
                "transaction_total": 4850.0,
                "transaction_avg": 606.25,
                "date_min": "2018-04-10",
                "date_max": "2018-04-12",
                "cards": [f"CARD_{client_id[-4:]}_1", f"CARD_{client_id[-4:]}_2"],
                "devices": [f"DEV_{client_id[-4:]}_A"],
                "email_domains": ["protonmail.com", "gmail.com"],
                "prior_fraud_cases": []
            }]

        elif query_name == "get_ring_neighbors":
            return [{
                "ring_neighbors": [
                    {"client_id": f"CLI-RING-{client_id[-4:]}-1", "shared_type": "SHARED_DEVICE", "ring_score": 0.82},
                    {"client_id": f"CLI-RING-{client_id[-4:]}-2", "shared_type": "SHARED_EMAIL", "ring_score": 0.74}
                ]
            }]

        elif query_name == "find_similar_closed_cases":
            return [{
                "similar_cases": [
                    {"case_id": "CASE-CLOSED-101", "typology_id": "TYP-01", "similarity_score": 0.89},
                    {"case_id": "CASE-CLOSED-204", "typology_id": "TYP-02", "similarity_score": 0.76}
                ]
            }]

        elif query_name == "get_policy_for_typology":
            typology_id = params.get("typology_id", "TYP-01")
            return [{
                "typology_id": typology_id,
                "rules": [
                    {"rule_id": "PR-102", "rule_name": "Velocity Attack Containment", "immediate_action": True},
                    {"rule_id": "PR-204", "rule_name": "Mandatory Step-Up Challenge", "immediate_action": False}
                ],
                "allowed_actions": [
                    {"action_id": "block_card", "approval_role": "senior_analyst"},
                    {"action_id": "request_stepup_auth", "approval_role": None}
                ]
            }]

        elif query_name == "get_case_subgraph":
            return [{
                "Case": [{"v_id": case_id, "v_type": "FraudCase", "attributes": {"narrative": "Simulated case narrative"}}],
                "Client": [{"v_id": client_id, "v_type": "Client", "attributes": {}}],
                "Transactions": [
                    {"v_id": f"TXN-{case_id[-3:]}-1", "v_type": "Transaction", "attributes": {"amount": 1200.0}},
                    {"v_id": f"TXN-{case_id[-3:]}-2", "v_type": "Transaction", "attributes": {"amount": 1800.0}}
                ],
                "Evidence": [
                    {"v_id": f"EV-{case_id[-3:]}-1", "v_type": "EvidenceItem", "attributes": {"description": "Velocity burst detected"}}
                ],
                "Typologies": [
                    {"v_id": "TYP-01", "v_type": "TypologyPattern", "attributes": {"typology_name": "Card-Not-Present Velocity Attack"}}
                ],
                "Actions": [
                    {"v_id": "ACT_BLOCK", "v_type": "ActionType", "attributes": {"action_name": "block_card"}}
                ],
                "Policies": [
                    {"v_id": "PR-102", "v_type": "PolicyRule", "attributes": {"rule_name": "Velocity Attack Containment"}}
                ],
                "SupportsEdges": [{"from_id": f"EV-{case_id[-3:]}-1", "to_id": "TYP-01", "e_type": "SUPPORTS", "attributes": {}}],
                "ContradictsEdges": [],
                "EvidenceEdges": [{"from_id": case_id, "to_id": f"EV-{case_id[-3:]}-1", "e_type": "HAS_EVIDENCE", "attributes": {}}],
                "ActionEdges": [{"from_id": case_id, "to_id": "ACT_BLOCK", "e_type": "TOOK_ACTION", "attributes": {}}]
            }]

        return []

    def getVerticesById(self, vertex_type: str, vertex_id: str) -> list:
        key = f"{vertex_type}:{vertex_id}"
        if key in self._vertices:
            return [self._vertices[key]]
        return [{"v_id": vertex_id, "v_type": vertex_type, "attributes": {}}]

    def upsertVertex(self, vertex_type: str, vertex_id: str, attributes: Optional[dict] = None):
        key = f"{vertex_type}:{vertex_id}"
        self._vertices[key] = {"v_id": vertex_id, "v_type": vertex_type, "attributes": attributes or {}}
        return 1

    def upsertEdge(self, source_type: str, source_id: str, edge_type: str,
                   target_type: str, target_id: str, attributes: Optional[dict] = None):
        self._edges.append({
            "from_type": source_type, "from_id": source_id,
            "e_type": edge_type,
            "to_type": target_type, "to_id": target_id,
            "attributes": attributes or {}
        })
        return 1

    def upsertVertices(self, vertex_type: str, vertices: list):
        for v in vertices:
            v_id = v.get("v_id") or v.get("id") or str(len(self._vertices))
            self.upsertVertex(vertex_type, v_id, v)
        return len(vertices)

    def upsertEdges(self, edge_type: str, edges: list):
        return len(edges)


def get_tg_connection(allow_fallback: bool = True) -> Any:
    """
    Create and return a pyTigerGraph connection using .env config.
    If .env is incomplete or connection fails and allow_fallback is True,
    returns an in-memory MockTigerGraphConnection.
    """
    errors = validate_config(config, require_tg=True, require_llm=False)
    if errors or tg is None:
        if allow_fallback:
            return MockTigerGraphConnection()
        raise RuntimeError(f"TigerGraph config errors: {'; '.join(errors)}")

    try:
        conn = tg.TigerGraphConnection(
            host=config.tigergraph.host,
            graphname=config.tigergraph.graphname,
            username=config.tigergraph.username,
            password=config.tigergraph.password,
            restppPort=str(config.tigergraph.rest_port),
            gsPort=str(config.tigergraph.gs_port),
        )
        try:
            conn.getToken(conn.createSecret())
        except Exception:
            pass
        return conn
    except Exception as e:
        if allow_fallback:
            print(f"[!] Warning: TigerGraph live connection failed ({e}). Using mock connection.")
            return MockTigerGraphConnection()
        raise


def verify_connection(conn: Any) -> dict:
    """Verify the TigerGraph connection is working. Returns version info."""
    try:
        version = conn.getVersion()
        schema = conn.getSchema()
        vertex_types = list(schema.get("VertexTypes", []))
        edge_types = list(schema.get("EdgeTypes", []))
        return {
            "status": "connected",
            "version": version,
            "vertex_type_count": len(vertex_types),
            "edge_type_count": len(edge_types),
            "vertex_types": [v.get("Name", "") for v in vertex_types],
            "edge_types": [e.get("Name", "") for e in edge_types],
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
