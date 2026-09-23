"""
Unit tests for TigerGraph MCP client integration.
Verifies compatibility with official tigergraph-mcp package
(https://github.com/tigergraph/tigergraph-mcp).
"""

import pytest
from agent.mcp_client import get_mcp_client, TigerGraphMCPClient
from config import config


def test_mcp_client_initialization():
    """Verify TigerGraphMCPClient initializes with default profile."""
    client = get_mcp_client()
    assert client is not None
    assert client.profile == "default"
    assert client.graph_name == "HHGOA_IEEE"


def test_mcp_client_schema_retrieval():
    """Verify MCP client retrieves schema with expected fraud vertices."""
    client = get_mcp_client()
    schema = client.get_schema()
    assert "VertexTypes" in schema
    assert "EdgeTypes" in schema

    vertex_names = [v.get("Name") for v in schema["VertexTypes"]]
    assert "Client" in vertex_names
    assert "FraudCase" in vertex_names
    assert "Transaction" in vertex_names
    assert "PolicyRule" in vertex_names


def test_mcp_client_installed_query():
    """Verify run_installed_query executes client context query."""
    client = get_mcp_client()
    result = client.run_installed_query(
        "get_client_context",
        params={"client_id": "CLI-TEST-001"}
    )
    assert result is not None
    assert isinstance(result, (list, dict))
    if isinstance(result, list) and len(result) > 0:
        assert "client_id" in result[0]


def test_mcp_client_upsert_vertex():
    """Verify upsert_vertex executes without error."""
    client = get_mcp_client()
    res = client.upsert_vertex(
        "FraudCase",
        "CASE-TEST-MCP-01",
        attributes={"status": "decided"}
    )
    assert res is not None
