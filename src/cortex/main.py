"""Cortex MCP server entry point.

Run with: uv run python -m cortex.main
"""

from cortex.config import CortexConfig
from cortex.graph.manager import GraphManager
from cortex.index.manager import IndexManager
from cortex.mcp.server import init_server


def main() -> None:
    config = CortexConfig()
    index = IndexManager(config)
    graph = GraphManager(config.index.graph_path)
    server = init_server(config=config, index=index, graph=graph)
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
