#!/usr/bin/env python3
"""
abby-normal MCP server for Claude Code.

Exposes abby_recall and abby_save tools via the Model Context Protocol,
giving Claude Code the same native memory access that OpenCode gets
through its plugin system.

Run: ~/code/abby-normal/.venv/bin/python3 ~/code/abby-normal/mcp/server.py
"""

import json
import os
import subprocess
import sys

# Auto-activate venv if not already in it
_ABBY_VENV = os.path.expanduser("~/code/abby-normal/.venv")
if not os.environ.get("ABBY_NORMAL_IN_VENV") and os.path.isdir(_ABBY_VENV):
    result = subprocess.run(
        [os.path.join(_ABBY_VENV, "bin", "python3"), __file__] + sys.argv[1:],
        env={**os.environ, "ABBY_NORMAL_IN_VENV": "1"},
    )
    sys.exit(result.returncode)

from mcp.server.fastmcp import FastMCP

MEMORY_QUERY = os.path.expanduser("~/.local/bin/memory-query")


def _run_memory_query(*args):
    result = subprocess.run(
        [MEMORY_QUERY, *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"exit code {result.returncode}")
    return result.stdout.strip()


mcp = FastMCP(
    name="abby-normal",
    instructions=(
        "abby-normal is a SQLite-backed memory system for AI agents. "
        "Use abby_recall to search for existing memories before starting work. "
        "Use abby_save to persist non-obvious learnings, decisions, or patterns. "
        "Default is to NOT save — only save when it would measurably help a future session."
    ),
)


@mcp.tool()
def abby_recall(query: str) -> str:
    """Search abby-normal for memories relevant to the current work. Use at session start with the project name or a relevant keyword. ALSO use this before calling abby_save to check that a candidate memory is not already stored."""
    try:
        output = _run_memory_query("search", query, "--limit=10")
        if not output or output == "[]":
            return "No relevant memories found."
        entries = json.loads(output)
        if not entries:
            return "No relevant memories found."

        lines = []
        for e in entries:
            proj = f" [{e['project_id']}]" if e.get("project_id") else ""
            lines.append(f"**{e['title']}**{proj}")
            excerpt = e.get("excerpt") or e.get("content", "")[:200]
            if excerpt:
                lines.append(excerpt.strip())
            lines.append("")

        return "\n".join(lines).strip()
    except Exception as e:
        return f"Memory query failed: {e}"


@mcp.tool()
def abby_save(title: str, content: str, project: str) -> str:
    """Save a memory to abby-normal. DO NOT use this for routine work, code edits, or things already obvious from the code. Only call when ALL are true: (1) a specific decision was made, a non-obvious gotcha was hit, or a reusable pattern emerged; (2) you have already called abby_recall to confirm this is not a duplicate; (3) deleting this memory tomorrow would measurably worsen a future session. Default is to NOT save. One memory per real lesson."""
    try:
        _run_memory_query(
            "add",
            f"--title={title}",
            f"--content={content}",
            f"--project={project}",
        )
        return f"Saved: {title}"
    except Exception as e:
        return f"Save failed: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
