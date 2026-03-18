"""Profile context usage of the Cortex MCP server on initial load.

Estimates how many tokens the MCP tool definitions, instructions, and
resources consume in the client's context window at startup.
"""

from __future__ import annotations

import asyncio
import json


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English + JSON."""
    return len(text) // 4


def profile_server() -> dict:
    """Introspect the MCP server and return context usage breakdown."""
    from cortex.config import CortexConfig
    from cortex.mcp.server import init_server, mcp

    config = CortexConfig()
    init_server(config=config)

    tools = asyncio.run(mcp.list_tools())

    instructions_text = mcp.instructions or ""
    instructions_tokens = _estimate_tokens(instructions_text)

    tool_details = []
    total_tool_tokens = 0

    for t in tools:
        mcp_tool = t.to_mcp_tool()
        serialized = mcp_tool.model_dump_json()

        name = t.name
        desc = t.description or ""
        schema_json = json.dumps(t.parameters, indent=2) if t.parameters else "{}"

        desc_tokens = _estimate_tokens(desc)
        schema_tokens = _estimate_tokens(schema_json)
        wire_tokens = _estimate_tokens(serialized)

        tool_details.append({
            "name": name,
            "desc_chars": len(desc),
            "schema_chars": len(schema_json),
            "wire_chars": len(serialized),
            "wire_tokens": wire_tokens,
            "desc_tokens": desc_tokens,
            "schema_tokens": schema_tokens,
        })
        total_tool_tokens += wire_tokens

    total_tokens = instructions_tokens + total_tool_tokens

    return {
        "instructions": {
            "text": instructions_text,
            "chars": len(instructions_text),
            "tokens": instructions_tokens,
        },
        "tools": {
            "count": len(tools),
            "total_tokens": total_tool_tokens,
            "details": sorted(tool_details, key=lambda t: t["wire_tokens"], reverse=True),
        },
        "total": {
            "tokens": total_tokens,
            "pct_of_200k": round(total_tokens / 200_000 * 100, 2),
        },
    }


def print_profile() -> None:
    """Print a formatted context profile report."""
    data = profile_server()

    print("=" * 60)
    print("  Cortex MCP — Context Profile")
    print("=" * 60)

    # Instructions
    inst = data["instructions"]
    print(f"\nInstructions: {inst['chars']} chars  (~{inst['tokens']} tokens)")
    if inst["text"]:
        preview = inst["text"][:80].replace("\n", " ")
        print(f'  "{preview}{"..." if len(inst["text"]) > 80 else ""}"')

    # Tools summary
    tools = data["tools"]
    print(f"\nTools: {tools['count']} registered  (~{tools['total_tokens']} tokens)")
    print()

    # Table header
    header = f"  {'Tool':<30} {'Desc':>6} {'Schema':>8} {'Wire':>8} {'~Tokens':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for t in tools["details"]:
        print(
            f"  {t['name']:<30} {t['desc_chars']:>6} {t['schema_chars']:>8} "
            f"{t['wire_chars']:>8} {t['wire_tokens']:>8}"
        )

    # Total
    print()
    total = data["total"]
    print(f"  Total estimated context: ~{total['tokens']} tokens")
    print(f"  % of 200k window:        {total['pct_of_200k']}%")
    print()

    # Top consumers
    print("  Top 5 by token cost:")
    for i, t in enumerate(tools["details"][:5], 1):
        print(f"    {i}. {t['name']} (~{t['wire_tokens']} tokens)")

    print()
