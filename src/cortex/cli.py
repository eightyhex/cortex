"""Cortex CLI — manage the MCP server.

Commands:
    cortex serve        Run the HTTP server (foreground)
    cortex install      Install LaunchAgent + configure Claude apps
    cortex uninstall    Remove LaunchAgent + MCP configs
    cortex restart      Restart the running server
    cortex status       Check server status
    cortex stdio        Run in stdio mode (single client, used by MCP directly)
"""

from __future__ import annotations

import argparse
import json
import os
import plistlib
import logging
import shutil
import subprocess
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

DEFAULT_PORT = 8757
LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per file
LOG_BACKUP_COUNT = 3  # keep 3 rotated files (20 MB total max)
LAUNCHD_LOG_MAX_AGE_DAYS = 7
LAUNCHAGENT_LABEL = "com.cortex.mcp-server"
LAUNCHAGENT_PATH = Path.home() / "Library/LaunchAgents" / f"{LAUNCHAGENT_LABEL}.plist"
CLAUDE_DESKTOP_CONFIG = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
CLAUDE_CODE_CONFIG = Path.home() / ".claude.json"


def _server_url(port: int) -> str:
    return f"http://127.0.0.1:{port}/mcp"


def _is_dev_checkout() -> bool:
    """True if running from a git checkout (development mode)."""
    # Check if we're inside the cortex source tree
    cli_file = Path(__file__).resolve()
    git_dir = cli_file.parent.parent.parent / ".git"
    return git_dir.is_dir()


def _project_dir() -> Path:
    """Return the project root (only meaningful in dev mode)."""
    return Path(__file__).resolve().parent.parent.parent


def _build_plist(port: int) -> dict:
    """Build the LaunchAgent plist dict."""
    if _is_dev_checkout():
        uv = shutil.which("uv") or "/opt/homebrew/bin/uv"
        prog_args = [
            uv, "run", "--directory", str(_project_dir()),
            "python", "-m", "cortex", "serve", "--port", str(port),
        ]
    else:
        # Installed via uv tool — use the binary directly
        cortex_bin = shutil.which("cortex")
        if not cortex_bin:
            print("Error: 'cortex' binary not found in PATH.", file=sys.stderr)
            sys.exit(1)
        prog_args = [cortex_bin, "serve", "--port", str(port)]

    # Real logging goes through RotatingFileHandler (server.log), but route
    # launchd stdout/stderr to files so crashes and uncaught exceptions
    # aren't lost.  These are cleaned up on each server start.
    log_dir = Path.home() / ".local/share/cortex"
    return {
        "Label": LAUNCHAGENT_LABEL,
        "ProgramArguments": prog_args,
        "RunAtLoad": True,
        "KeepAlive": True,
        "StandardOutPath": str(log_dir / "launchd-stdout.log"),
        "StandardErrorPath": str(log_dir / "launchd-stderr.log"),
    }


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def _agent_is_loaded() -> bool:
    result = _launchctl("list")
    return LAUNCHAGENT_LABEL in result.stdout


def _uid() -> str:
    return str(os.getuid())


# ── Commands ──────────────────────────────────────────────────────────────


def _clean_launchd_logs() -> None:
    """Truncate launchd stdout/stderr logs if older than LAUNCHD_LOG_MAX_AGE_DAYS."""
    log_dir = Path.home() / ".local/share/cortex"
    cutoff = time.time() - (LAUNCHD_LOG_MAX_AGE_DAYS * 86400)
    for name in ("launchd-stdout.log", "launchd-stderr.log"):
        log_file = log_dir / name
        if log_file.exists() and log_file.stat().st_mtime < cutoff:
            log_file.write_text("")


def _setup_log_rotation() -> None:
    """Configure rotating log file for stdout/stderr when running as a daemon."""
    log_dir = Path.home() / ".local/share/cortex"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "server.log"

    handler = RotatingFileHandler(
        log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT,
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    # Redirect uvicorn/fastmcp output through the rotating handler
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "fastmcp"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False


def cmd_serve(args: argparse.Namespace) -> None:
    """Run the MCP server in the foreground."""
    from cortex.config import CortexConfig
    from cortex.graph.manager import GraphManager
    from cortex.index.manager import IndexManager
    from cortex.mcp.server import init_server

    _setup_log_rotation()
    _clean_launchd_logs()

    config = CortexConfig()
    index = IndexManager(config)
    graph = GraphManager(config.index.graph_path)
    server = init_server(config=config, index=index, graph=graph)
    server.run(transport="streamable-http", host="127.0.0.1", port=args.port)


def cmd_stdio(args: argparse.Namespace) -> None:
    """Run the MCP server in stdio mode (single client)."""
    from cortex.config import CortexConfig
    from cortex.graph.manager import GraphManager
    from cortex.index.manager import IndexManager
    from cortex.mcp.server import init_server

    config = CortexConfig()
    index = IndexManager(config)
    graph = GraphManager(config.index.graph_path)
    server = init_server(config=config, index=index, graph=graph)
    server.run(transport="stdio")


def cmd_install(args: argparse.Namespace) -> None:
    """Install LaunchAgent and configure Claude apps."""
    port = args.port
    url = _server_url(port)

    # 1. Write LaunchAgent plist
    plist = _build_plist(port)
    LAUNCHAGENT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LAUNCHAGENT_PATH, "wb") as f:
        plistlib.dump(plist, f)
    print(f"Wrote LaunchAgent: {LAUNCHAGENT_PATH}")

    if _is_dev_checkout():
        print(f"  (dev mode — runs from source at {_project_dir()})")

    # 2. Load the agent
    if _agent_is_loaded():
        _launchctl("bootout", f"gui/{_uid()}/{LAUNCHAGENT_LABEL}")
    _launchctl("bootstrap", f"gui/{_uid()}", str(LAUNCHAGENT_PATH))
    print("LaunchAgent loaded (server starting).")

    # 3. Configure Claude Code
    _configure_claude_code(url)

    # 4. Configure Claude Desktop
    _configure_claude_desktop(url)

    print(f"\nCortex MCP server installed on port {port}.")
    print("Restart Claude Code and Claude Desktop to pick up the changes.")


def _configure_claude_code(url: str) -> None:
    """Add/update cortex in Claude Code's MCP config."""
    claude_code = shutil.which("claude")
    if not claude_code:
        print("  Claude Code CLI not found — skipping Claude Code config.")
        return

    # Remove existing (may be stdio)
    subprocess.run(
        [claude_code, "mcp", "remove", "cortex", "-s", "user"],
        capture_output=True, text=True,
    )
    result = subprocess.run(
        [claude_code, "mcp", "add", "cortex", "-s", "user", "--transport", "http", url],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"  Claude Code: configured cortex -> {url}")
    else:
        print(f"  Claude Code: failed to configure — {result.stderr.strip()}")


def _configure_claude_desktop(url: str) -> None:
    """Add/update cortex in Claude Desktop's config."""
    if not CLAUDE_DESKTOP_CONFIG.parent.exists():
        print("  Claude Desktop not found — skipping.")
        return

    config: dict = {}
    if CLAUDE_DESKTOP_CONFIG.exists():
        with open(CLAUDE_DESKTOP_CONFIG) as f:
            config = json.load(f)

    servers = config.setdefault("mcpServers", {})
    # Claude Desktop doesn't support HTTP transport natively.
    # Use mcp-remote as a stdio-to-HTTP bridge so both Claude Code and
    # Claude Desktop share the same background server process.
    servers["cortex"] = {
        "command": "npx",
        "args": ["mcp-remote@latest", url, "--allow-http"],
    }

    with open(CLAUDE_DESKTOP_CONFIG, "w") as f:
        json.dump(config, f, indent=2)
    print(f"  Claude Desktop: configured cortex via mcp-remote -> {url}")


def cmd_uninstall(args: argparse.Namespace) -> None:
    """Remove LaunchAgent and MCP configs."""
    # 1. Unload and remove LaunchAgent
    if _agent_is_loaded():
        _launchctl("bootout", f"gui/{_uid()}/{LAUNCHAGENT_LABEL}")
        print("LaunchAgent unloaded.")
    if LAUNCHAGENT_PATH.exists():
        LAUNCHAGENT_PATH.unlink()
        print(f"Removed {LAUNCHAGENT_PATH}")

    # 2. Remove from Claude Code
    claude_code = shutil.which("claude")
    if claude_code:
        subprocess.run(
            [claude_code, "mcp", "remove", "cortex", "-s", "user"],
            capture_output=True, text=True,
        )
        print("  Claude Code: removed cortex MCP config.")

    # 3. Remove from Claude Desktop
    if CLAUDE_DESKTOP_CONFIG.exists():
        with open(CLAUDE_DESKTOP_CONFIG) as f:
            config = json.load(f)
        if "cortex" in config.get("mcpServers", {}):
            del config["mcpServers"]["cortex"]
            with open(CLAUDE_DESKTOP_CONFIG, "w") as f:
                json.dump(config, f, indent=2)
            print("  Claude Desktop: removed cortex MCP config.")

    print("\nCortex MCP server uninstalled.")


def cmd_restart(args: argparse.Namespace) -> None:
    """Restart the running server (picks up code changes in dev mode)."""
    if not _agent_is_loaded():
        print("LaunchAgent not loaded. Run 'cortex install' first.")
        sys.exit(1)

    _launchctl("kickstart", "-k", f"gui/{_uid()}/{LAUNCHAGENT_LABEL}")
    print("Cortex server restarting.")


def cmd_profile(args: argparse.Namespace) -> None:
    """Profile context token usage of the MCP server on initial load."""
    from cortex.profile import print_profile

    print_profile()


def cmd_status(args: argparse.Namespace) -> None:
    """Check if the server is running."""
    if _agent_is_loaded():
        result = _launchctl("list", LAUNCHAGENT_LABEL)
        # Parse PID from output
        for line in result.stdout.splitlines():
            if '"PID"' in line:
                pid = line.strip().rstrip(";").split("=")[-1].strip()
                print(f"Cortex server is running (PID {pid}).")
                return
        print("Cortex server is loaded (status unknown).")
    else:
        print("Cortex server is not running.")
        if not LAUNCHAGENT_PATH.exists():
            print("Run 'cortex install' to set it up.")


# ── Entry point ───────────────────────────────────────────────────────────


def cli() -> None:
    parser = argparse.ArgumentParser(
        prog="cortex",
        description="Cortex — local-first AI-native second brain",
    )
    sub = parser.add_subparsers(dest="command")

    # serve
    p_serve = sub.add_parser("serve", help="Run the HTTP server (foreground)")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_serve.set_defaults(func=cmd_serve)

    # stdio
    p_stdio = sub.add_parser("stdio", help="Run in stdio mode (single client)")
    p_stdio.set_defaults(func=cmd_stdio)

    # install
    p_install = sub.add_parser("install", help="Install LaunchAgent + configure Claude apps")
    p_install.add_argument("--port", type=int, default=DEFAULT_PORT)
    p_install.set_defaults(func=cmd_install)

    # uninstall
    p_uninstall = sub.add_parser("uninstall", help="Remove LaunchAgent + MCP configs")
    p_uninstall.set_defaults(func=cmd_uninstall)

    # restart
    p_restart = sub.add_parser("restart", help="Restart the server (picks up code changes)")
    p_restart.set_defaults(func=cmd_restart)

    # status
    p_status = sub.add_parser("status", help="Check server status")
    p_status.set_defaults(func=cmd_status)

    # profile
    p_profile = sub.add_parser("profile", help="Profile MCP context token usage")
    p_profile.set_defaults(func=cmd_profile)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    args.func(args)
