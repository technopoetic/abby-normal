# abby-normal

A global memory system for AI agents with unified storage, full-text search, **semantic vector search**, and multi-agent orchestration.

Named after the "Abby Normal" brain in Young Frankenstein.

## What It Does

abby-normal stores knowledge, decisions, and patterns from AI-assisted development sessions in a queryable SQLite database. It includes:

- **Unified memory**: Single table for all knowledge types with FTS search
- **Semantic search**: Find entries by meaning, not just keywords (via sqlite-vec)
- **Hybrid search**: Combined FTS5 + semantic similarity for best results
- **Multi-agent orchestration**: Coordinate specialist agents with wave-based execution
- **Cross-project**: Search learnings across all your projects
- **Local-first**: No API keys, no server, everything in a single SQLite file

## Quick Start

```bash
# Setup
cd ~/code/abby-normal
python3 setup.py          # Creates ~/.local/share/abby-normal/memory.db

# Install semantic search dependencies (recommended)
pip install pysqlite3-binary sqlite-vec sentence-transformers

# Backfill embeddings for existing entries
python3 backfill_embeddings.py

# Create symlinks
ln -s ~/code/abby-normal/memory_query.py ~/.local/bin/memory-query
ln -s ~/code/abby-normal/orchestration.py ~/.local/bin/orchestration

# Search (auto-selects hybrid or FTS-only based on available dependencies)
memory-query search authentication
memory-query search "Stripe webhook error handling"

# Add memory
memory-query add --title="..." --content="..." --project=myproject --tags=Python
```

## Search

A single `search` command that automatically uses the best strategy available:

- **With sqlite-vec installed**: hybrid FTS5 + semantic search (keyword matches AND meaning-based matches)
- **Without sqlite-vec**: FTS5 keyword search only

Recent memories get a ranking boost (+0.2 for last 7 days, +0.1 for last 30 days).

```bash
memory-query search "payment failure handling"
```

This finds entries containing "payment" or "failure" (FTS5) **and** entries about "Stripe webhook errors" or "credit card retry logic" (semantic), with entries found by both getting a ranking boost.

## Database

Location: `~/.local/share/abby-normal/memory.db`

Schema:
- `memory_entries`: All knowledge with FTS5 search
- `memory_embeddings`: 384-dim vector index (sqlite-vec)
- `projects` + `components`: Project metadata
- Orchestration tables for multi-agent coordination

## Dependencies

**Core** (no external packages needed):
- Python 3.8+
- SQLite 3.25+

**Semantic search** (optional but recommended):
- `pysqlite3-binary` — SQLite with extension loading
- `sqlite-vec` — Vector similarity search
- `sentence-transformers` — Local embedding model (all-MiniLM-L6-v2, ~80MB)

## Automatic Integration via Hooks

abby-normal can inject memories automatically at session start — no manual `memory-query search` needed.

### Claude Code

Add to `~/.claude/settings.json`:

```json
"hooks": {
  "SessionStart": [
    {
      "hooks": [
        {
          "type": "command",
          "command": "/path/to/abby-normal/.venv/bin/python3",
          "args": ["/path/to/abby-normal/hooks/session_start.py"],
          "timeout": 15,
          "statusMessage": "Loading memories..."
        }
      ]
    }
  ],
  "Stop": [
    {
      "hooks": [
        {
          "type": "prompt",
          "prompt": "If this session produced any new learnings worth keeping — a decision, a pattern, a gotcha — save them now with `memory-query add --title=... --content=... --project=...` before stopping. Skip if nothing new happened this turn.",
          "timeout": 30
        }
      ]
    }
  ]
}
```

`hooks/session_start.py` reads the current working directory, resolves the project name via aliases, runs `search` with the project as a boost term, and returns the results as `additionalContext`. Cross-project memories surface when semantically relevant.

### OpenCode

Place `hooks/abby-normal.js` in `~/.config/opencode/plugins/` — it auto-loads at startup.

Requires `@opencode-ai/plugin` in `~/.config/opencode/package.json`:

```json
{ "dependencies": { "@opencode-ai/plugin": "^1.4.0" } }
```

The plugin provides:
- **`experimental.chat.messages.transform`** — injects relevant memories into the first user message of each session (equivalent to Claude Code's `additionalContext`)
- **`experimental.session.compacting`** — re-injects memories at context compaction so they survive compression
- **`abby_recall` tool** — Claude can search memories explicitly: `abby_recall({ query: "mekanik stripe" })`
- **`abby_save` tool** — Claude can save memories explicitly: `abby_save({ title, content, project })`

### Project name mapping

Both hooks derive a project ID from the current directory basename. By default, the basename is used as-is (e.g., working in `~/code/myapp` searches for "myapp").

For projects spanning multiple directories, add aliases:

```bash
# Map multiple directories to one project
memory-query alias add myapp-frontend myapp
memory-query alias add myapp-api myapp

# List aliases
memory-query alias list

# Remove an alias
memory-query alias remove myapp-frontend
```

Aliases are stored in the abby-normal database, not in source files.

## Files

```
abby-normal/
├── schema.sql              # Database schema
├── memory_query.py         # Query CLI (v3.0 with semantic search)
├── embeddings.py           # Shared embedding utilities
├── backfill_embeddings.py  # One-time backfill script
├── orchestration.py        # Multi-agent coordination
├── memory_export.py        # Export to JSON
├── requirements.txt        # Python dependencies
├── hooks/
│   ├── session_start.py    # Claude Code SessionStart hook
│   └── abby-normal.js      # OpenCode plugin
└── README.md               # This file
```

## Contributing

This is a personal project, but suggestions welcome via issues.

---

*"It's alive!"* — Young Frankenstein
