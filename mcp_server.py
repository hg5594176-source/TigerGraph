"""
TigerGraph MCP Server Entrypoint.
Launches the official tigergraph-mcp server (https://github.com/tigergraph/tigergraph-mcp)
configured for the Agentic Fraud Investigation System (graph: HHGOA_IEEE).

Usage:
  # stdio mode (for Claude Desktop, Cursor, VS Code Copilot):
  python mcp_server.py

  # HTTP / SSE transport (for multi-client or web agents):
  python mcp_server.py --transport streamable-http --host 0.0.0.0 --port 8000
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Ensure .env is loaded before server startup
PROJECT_ROOT = Path(__file__).resolve().parent
load_dotenv(PROJECT_ROOT / ".env")

try:
    from tigergraph_mcp import serve
    from tigergraph_mcp.connection_manager import ConnectionManager
except ImportError:
    print("[ERROR] tigergraph-mcp is not installed. Run: pip install tigergraph-mcp")
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="TigerGraph MCP Server for Fraud Investigation System"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="MCP Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("MCP_HOST", "127.0.0.1"),
        help="Bind address for HTTP transports (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.getenv("MCP_PORT", "8000")),
        help="Port for HTTP transports (default: 8000)",
    )
    parser.add_argument(
        "--mount-path",
        default="/mcp",
        help="Mount path for HTTP transports (default: /mcp)",
    )
    parser.add_argument(
        "--env-file",
        default=str(PROJECT_ROOT / ".env"),
        help="Path to .env configuration file",
    )

    args = parser.parse_args()

    # Pre-load profiles
    if os.path.exists(args.env_file):
        ConnectionManager.load_profiles(args.env_file)

    # Ensure TG_GRAPHNAME default is HHGOA_IEEE if not specified
    if not os.getenv("TG_GRAPHNAME"):
        os.environ["TG_GRAPHNAME"] = "HHGOA_IEEE"

    print(f"[*] Starting TigerGraph MCP Server (transport={args.transport})...")
    if args.transport != "stdio":
        print(f"[*] Listening on http://{args.host}:{args.port}{args.mount_path}")

    try:
        asyncio.run(
            serve(
                transport=args.transport,
                host=args.host,
                port=args.port,
                mount_path=args.mount_path,
            )
        )
    except KeyboardInterrupt:
        print("\n[*] TigerGraph MCP Server shut down.")


if __name__ == "__main__":
    main()
