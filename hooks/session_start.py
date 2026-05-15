#!/usr/bin/env python3
"""
Claude Code / OpenCode SessionStart hook.

Reads session context from stdin, resolves the working directory to a project
via abby-normal aliases, queries for relevant memories, and returns them as
additionalContext so agents start every session informed.
"""

import json
import os
import subprocess
import sys

MEMORY_QUERY = os.path.expanduser("~/code/abby-normal/.venv/bin/python3")
MEMORY_SCRIPT = os.path.expanduser("~/code/abby-normal/memory_query.py")


def _run_memory_query(*args):
    return subprocess.run(
        [MEMORY_QUERY, MEMORY_SCRIPT, *args],
        capture_output=True,
        text=True,
        env={**os.environ, "ABBY_NORMAL_IN_VENV": "1"},
    )


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    cwd = data.get("cwd", "")
    dirname = os.path.basename(cwd.rstrip("/"))

    try:
        resolve = _run_memory_query("resolve-project", dirname)
        project = resolve.stdout.strip() if resolve.returncode == 0 and resolve.stdout.strip() else dirname
    except (OSError, FileNotFoundError):
        project = dirname

    try:
        result = _run_memory_query("search", project, "--limit=5")
    except (OSError, FileNotFoundError):
        sys.exit(0)

    if result.returncode != 0 or not result.stdout.strip():
        sys.exit(0)

    try:
        entries = json.loads(result.stdout)
    except json.JSONDecodeError:
        sys.exit(0)

    if not entries:
        sys.exit(0)

    lines = [f"## Memories relevant to: {project}\n"]
    for e in entries:
        proj_label = f" [{e['project_id']}]" if e.get("project_id") else ""
        lines.append(f"**{e['title']}**{proj_label}")
        excerpt = e.get("excerpt") or e.get("content", "")[:200]
        if excerpt:
            lines.append(excerpt.strip())
        lines.append("")

    context = "\n".join(lines).strip()

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }))


if __name__ == "__main__":
    main()
