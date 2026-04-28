# abby-normal — Global Memory System for AI Agents

*Named after the "Abby Normal" brain from Young Frankenstein.*

## What This Is

A SQLite-backed memory system for AI agents. Stores learnings, decisions, and patterns across projects with FTS search. Also includes an optional multi-agent orchestration layer.

## Setup

```bash
python3 ~/code/abby-normal/setup.py   # Creates ~/.local/share/abby-normal/memory.db

# Symlinks for CLI access
ln -s ~/code/abby-normal/memory_query.py ~/.local/bin/memory-query
ln -s ~/code/abby-normal/orchestration.py ~/.local/bin/orchestration
ln -s ~/code/abby-normal/migrate_fts.py ~/.local/bin/migrate-abby-fts
```

Database lives at `~/.local/share/abby-normal/memory.db` — never delete it without explicit permission.

The database is git-tracked in `~/.config/opencode/`. After sessions, commit it there:
```bash
cd ~/.config/opencode && git add memory.db && git commit -m "Session: ..."
```

## Migrating an Existing Installation

If you installed before the FTS upgrade (porter stemmer + BM25 ranking), run once:
```bash
migrate-abby-fts
# or: python3 ~/code/abby-normal/migrate_fts.py
```

Idempotent — safe to run multiple times. Only the FTS index is rebuilt; data is untouched.

## CLI Commands

### Search
```bash
memory-query search <query>                          # BM25-ranked, porter-stemmed
memory-query search <query> --project=myproject      # Filter by project
memory-query search <query> --tags=Python,Testing    # Filter by tags (must match ALL)
memory-query search --project=myproject              # All entries for project (no query, date-ordered)
memory-query search <query> --limit=50               # Default limit is 20
```

**Search uses porter stemming** — `connect` matches `connection`, `connected`, `connecting`. Results
are ordered by BM25 relevance. Each result includes:
- `excerpt`: match context with matched terms in `[brackets]`
- `bm25_score`: relevance score (more negative = more relevant)

Filter-only searches (no query) return results ordered by `created_at` with no `excerpt`.

**FTS5 query syntax** is supported when detected (AND/OR/NOT/NEAR/quotes/`*` present):
```bash
memory-query search "redis cache"            # phrase — adjacent words
memory-query search 'redis OR keydb'         # either term
memory-query search 'cache NOT redis'        # first without second
memory-query search 'auth*'                  # prefix (use short prefixes — see note)
memory-query search 'NEAR(redis cache, 5)'   # within 5 tokens of each other
memory-query search 'title: migration'       # search specific column
```

> **Prefix + porter note**: the stemmer reduces words before indexing, so use short prefixes.
> `auth*` matches `authentication`; `authenticat*` does not (the stem doesn't share that prefix).

Otherwise, multi-word queries are treated as implicit AND — `redis cache` requires both terms.

### Add
```bash
memory-query add \
  --title="Short title" \
  --content="Full description" \
  --project=myproject \        # Optional
  --component=mycomponent \    # Optional, sub-project grouping
  --tags=Tag1,Tag2             # Optional
```

Entry IDs are auto-generated as `MEM-YYYYMMDD-HHMMSS-xxxxxx`. Do not supply IDs manually via CLI.

### Other
```bash
memory-query project <project_id>    # Project details + components
memory-query active-projects         # All projects with status='active'
memory-query vocabulary [--category=X]
```

## Database Schema (key facts)

- `memory_entries`: unified table for all knowledge — no forced type taxonomy
- `metadata` column: JSON blob; tags stored as `metadata.tags` array
- FTS via `memory_entries_fts` virtual table with triggers keeping it in sync
- `projects` and `components` tables: for filtering and organization
- Orchestration tables are separate (`orchestration_sessions`, `waves`, `agent_sessions`, etc.)

## Orchestration (Optional)

Wave-based multi-agent coordination. See `ORCHESTRATION_SETUP.md` for installation.

Agent definitions live in `agents/` — copy them to `~/.config/opencode/agents/` to activate:
```bash
cp ~/code/abby-normal/agents/*.md ~/.config/opencode/agents/
```

```bash
# CLI — orchestration.py (symlinked as `orchestration`)
orchestration create-session <project_id> "<description>" [--max-agents=N]
orchestration create-wave <session_id> <wave_number>
orchestration create-agent <session_id> <wave_id> <name> <type> "<task>"
orchestration validate-wave <wave_id> <session_id> <project_id>
```

In OpenCode: `Tab` to cycle agents → select Orchestrator, or `@orchestrator <task>`.

## Conventions

- Tags are optional. Entries without tags are fully searchable via FTS.
- Use `--project=` consistently — it's the primary grouping key across tools.
- Agents should never use raw SQL; always go through the CLI wrappers.
- The `memory-query` commands output JSON — pipe or parse accordingly.

## Personality

When appropriate, toss in a Young Frankenstein reference. Use sparingly.
