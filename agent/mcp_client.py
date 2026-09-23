"""
TigerGraph MCP Client Adapter.
Bridges LangGraph agent nodes with official tigergraph-mcp tools:
https://github.com/tigergraph/tigergraph-mcp

Provides high-level methods:
- run_installed_query (tigergraph__run_installed_query)
- get_neighbors (tigergraph__get_neighbors)
- search_top_k_similarity (tigergraph__search_top_k_similarity)
- upsert_vertex (tigergraph__add_node)
- upsert_edge (tigergraph__add_edge)
- get_schema (tigergraph__get_graph_schema)
- execute_gsql (tigergraph__gsql)

Includes intelligent fallback to pyTigerGraph / MockTigerGraphConnection
when running in offline/local testing mode.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config import config, validate_config
from schema.tg_connection import get_tg_connection

logger = logging.getLogger("tigergraph_mcp_client")

# Attempt importing official tigergraph_mcp tools
try:
    import tigergraph_mcp
    from tigergraph_mcp.tools import (
        query_tools,
        node_tools,
        edge_tools,
        schema_tools,
        vector_tools,
        gsql_tools,
    )
    from tigergraph_mcp.connection_manager import ConnectionManager
    HAS_TIGERGRAPH_MCP = True
except ImportError:
    HAS_TIGERGRAPH_MCP = False
    logger.warning("tigergraph-mcp package not installed or failed to import.")


def _run_async(coro):
    """Safely run an async coroutine from synchronous LangGraph nodes."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return loop.run_until_complete(coro)


def _extract_mcp_data(mcp_contents) -> Any:
    """Parse MCP TextContent response list into Python data dictionary/list."""
    if not mcp_contents:
        return None
    try:
        for content in mcp_contents:
            text = getattr(content, "text", str(content))
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                if parsed.get("status") == "error":
                    logger.warning(f"MCP Tool returned error status: {parsed.get('message')}")
                    return None
                if "data" in parsed:
                    data = parsed["data"]
                    if isinstance(data, dict) and "result" in data:
                        return data["result"]
                    return data
        return None
    except Exception as e:
        logger.debug(f"Failed to parse MCP response as JSON: {e}")
        return mcp_contents


class TigerGraphMCPClient:
    """
    Client for interacting with TigerGraph through official tigergraph-mcp tools
    with transparent fallback to pyTigerGraph/mock connection.
    """

    def __init__(self, profile: str = "default", graph_name: Optional[str] = None):
        self.profile = profile or config.tigergraph.profile or "default"
        self.graph_name = graph_name or config.tigergraph.graphname or "HHGOA_IEEE"
        self._fallback_conn = None
        self._use_mcp = HAS_TIGERGRAPH_MCP and bool(config.tigergraph.host)

    def _get_fallback(self):
        if self._fallback_conn is None:
            self._fallback_conn = get_tg_connection(allow_fallback=True)
        return self._fallback_conn

    def run_installed_query(self, query_name: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Execute installed GSQL query via tigergraph__run_installed_query or fallback."""
        params = params or {}
        if self._use_mcp:
            try:
                res = _run_async(
                    query_tools.run_installed_query(
                        query_name=query_name,
                        params=params,
                        profile=self.profile,
                        graph_name=self.graph_name,
                    )
                )
                data = _extract_mcp_data(res)
                if data is not None:
                    return data
            except Exception as e:
                logger.warning(f"MCP run_installed_query failed ({e}), falling back to direct connection.")

        # Fallback
        conn = self._get_fallback()
        return conn.runInstalledQuery(query_name, params=params)

    def get_neighbors(
        self,
        source_vertex_id: str,
        source_vertex_type: str = "Client",
        edge_types: Optional[List[str]] = None,
        target_vertex_types: Optional[List[str]] = None,
        max_hops: int = 2,
    ) -> Any:
        """Traverse neighbors via tigergraph__get_neighbors or fallback."""
        if self._use_mcp:
            try:
                res = _run_async(
                    query_tools.get_neighbors(
                        vertex_id=str(source_vertex_id),
                        vertex_type=source_vertex_type,
                        edge_types=edge_types,
                        target_vertex_types=target_vertex_types,
                        profile=self.profile,
                        graph_name=self.graph_name,
                    )
                )
                data = _extract_mcp_data(res)
                if data is not None:
                    return data
            except Exception as e:
                logger.warning(f"MCP get_neighbors failed ({e}), using fallback.")

        # Fallback to get_ring_neighbors query
        conn = self._get_fallback()
        return conn.runInstalledQuery(
            "get_ring_neighbors",
            params={"client_id": source_vertex_id, "hops": max_hops},
        )

    def upsert_vertex(self, vertex_type: str, vertex_id: str, attributes: Optional[Dict[str, Any]] = None) -> Any:
        """Upsert a vertex via tigergraph__add_node or fallback."""
        attributes = attributes or {}
        if self._use_mcp:
            try:
                res = _run_async(
                    node_tools.add_node(
                        vertex_type=vertex_type,
                        vertex_id=str(vertex_id),
                        attributes=attributes,
                        profile=self.profile,
                        graph_name=self.graph_name,
                    )
                )
                return _extract_mcp_data(res) or True
            except Exception as e:
                logger.warning(f"MCP add_node failed ({e}), using fallback.")

        conn = self._get_fallback()
        return conn.upsertVertex(vertex_type, str(vertex_id), attributes=attributes)

    def upsert_edge(
        self,
        from_vertex_type: str,
        from_vertex_id: str,
        to_vertex_type: str,
        to_vertex_id: str,
        edge_type: str,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Upsert an edge via tigergraph__add_edge or fallback."""
        attributes = attributes or {}
        if self._use_mcp:
            try:
                res = _run_async(
                    edge_tools.add_edge(
                        from_vertex_type=from_vertex_type,
                        from_vertex_id=str(from_vertex_id),
                        to_vertex_type=to_vertex_type,
                        to_vertex_id=str(to_vertex_id),
                        edge_type=edge_type,
                        attributes=attributes,
                        profile=self.profile,
                        graph_name=self.graph_name,
                    )
                )
                return _extract_mcp_data(res) or True
            except Exception as e:
                logger.warning(f"MCP add_edge failed ({e}), using fallback.")

        conn = self._get_fallback()
        return conn.upsertEdge(
            from_vertex_type,
            str(from_vertex_id),
            edge_type,
            to_vertex_type,
            str(to_vertex_id),
            attributes=attributes,
        )

    def get_schema(self) -> Dict[str, Any]:
        """Fetch graph schema via tigergraph__get_graph_schema or fallback."""
        if self._use_mcp:
            try:
                res = _run_async(
                    schema_tools.get_graph_schema(
                        profile=self.profile,
                        graph_name=self.graph_name,
                    )
                )
                data = _extract_mcp_data(res)
                if data and "schema" in data:
                    return data["schema"]
            except Exception as e:
                logger.warning(f"MCP get_graph_schema failed ({e}), using fallback.")

        conn = self._get_fallback()
        return conn.getSchema()

    def search_top_k_similarity(
        self,
        vertex_type: str,
        vector_attribute: str,
        query_vector: List[float],
        top_k: int = 5,
    ) -> Any:
        """Perform vector similarity search via tigergraph__search_top_k_similarity."""
        if self._use_mcp:
            try:
                res = _run_async(
                    vector_tools.search_top_k_similarity(
                        vertex_type=vertex_type,
                        vector_attribute=vector_attribute,
                        query_vector=query_vector,
                        top_k=top_k,
                        profile=self.profile,
                        graph_name=self.graph_name,
                    )
                )
                data = _extract_mcp_data(res)
                if data is not None:
                    return data
            except Exception as e:
                logger.warning(f"MCP search_top_k_similarity failed ({e})")
        return None

    def execute_gsql(self, command: str) -> str:
        """Execute raw GSQL command via tigergraph__gsql or fallback."""
        if self._use_mcp:
            try:
                res = _run_async(
                    gsql_tools.gsql(
                        command=command,
                        profile=self.profile,
                        graph_name=self.graph_name,
                    )
                )
                data = _extract_mcp_data(res)
                if data is not None:
                    return str(data)
            except Exception as e:
                logger.warning(f"MCP gsql execution failed ({e}), using fallback.")

        conn = self._get_fallback()
        if hasattr(conn, "gsql"):
            return conn.gsql(command)
        return ""


# Singleton instance
_client_instance: Optional[TigerGraphMCPClient] = None


def get_mcp_client(profile: str = "default", graph_name: Optional[str] = None) -> TigerGraphMCPClient:
    """Get or create singleton TigerGraphMCPClient."""
    global _client_instance
    if _client_instance is None:
        _client_instance = TigerGraphMCPClient(profile=profile, graph_name=graph_name)
    return _client_instance
