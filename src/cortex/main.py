"""Cortex MCP server entry point.

Run with: uv run python -m cortex.main
"""

from cortex.mcp.server import init_server


def main() -> None:
    server = init_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
