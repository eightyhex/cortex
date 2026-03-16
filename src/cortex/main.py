"""Cortex MCP server entry point (backward compatibility).

Prefer using the CLI directly: cortex serve / cortex install / etc.
This module is kept so `python -m cortex.main` and `python -m cortex.main --http` still work.
"""

from __future__ import annotations

import argparse

from cortex.config import CortexConfig
from cortex.graph.manager import GraphManager
from cortex.index.manager import IndexManager
from cortex.mcp.server import init_server

DEFAULT_PORT = 8757


def main() -> None:
    parser = argparse.ArgumentParser(description="Cortex MCP server")
    parser.add_argument(
        "--http", action="store_true",
        help="Run as streamable-http server (supports multiple clients)",
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT,
        help=f"Port for HTTP transport (default: {DEFAULT_PORT})",
    )
    args = parser.parse_args()

    config = CortexConfig()
    index = IndexManager(config)
    graph = GraphManager(config.index.graph_path)
    server = init_server(config=config, index=index, graph=graph)

    if args.http:
        server.run(transport="streamable-http", host="127.0.0.1", port=args.port)
    else:
        server.run(transport="stdio")


if __name__ == "__main__":
    main()
