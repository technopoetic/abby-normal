#!/usr/bin/env python3
"""
Claude Code / OpenCode SessionStart hook.

Reads session context from stdin, queries abby-normal for relevant memories,
and returns them as additionalContext so agents start every session informed.

Project name is used as a search term (not a hard --project= filter) so BM25
naturally boosts project-relevant entries while cross-project memories still surface.
"""

import json
import os
import subprocess
import sys

MEMORY_QUERY = os.path.expanduser("~/code/abby-normal/.venv/bin/python3")
MEMORY_SCRIPT = os.path.expanduser("~/code/abby-normal/memory_query.py")

# Map directory basenames to canonical project IDs used in memory entries
PROJECT_MAP = {
    "mekanik": "mekanik",
    "mekanik_vue": "mekanik",
    "mekanik_registration": "mekanik",
    "lora": "lora",
    "banking_software": "lora",
    "abby-normal": "abby-normal",
    "codegraph": "codegraph",
}


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        sys.exit(0)

    cwd = data.get("cwd", "")
    dirname = os.path.basename(cwd.rstrip("/"))
    project = PROJECT_MAP.get(dirname, dirname)

    result = subprocess.run(
        [MEMORY_QUERY, MEMORY_SCRIPT, "search-hybrid", project, "--limit=5"],
        capture_output=True,
        text=True,
        env={**os.environ, "ABBY_NORMAL_IN_VENV": "1"},
    )

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
