# abby-normal — Global Memory System for AI Agents

*Named after the "Abby Normal" brain from Young Frankenstein.*

## What This Is

A SQLite-backed memory system for AI agents. Stores learnings, decisions, and patterns across projects with FTS search **and semantic vector search**. Also includes an optional multi-agent orchestration layer.

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

For semantic search, backfill vector embeddings:
```bash
python3 ~/code/abby-normal/backfill_embeddings.py              # Embed all entries
python3 ~/code/abby-normal/backfill_embeddings.py --dry-run    # Preview first
```

## CLI Commands

### Search

Three search modes:

**Keyword search** — FTS5 with porter stemming and BM25 ranking:
```bash
memory-query search <query>                          # BM25-ranked, porter-stemmed
memory-query search <query> --project=myproject      # Filter by project
memory-query search <query> --tags=Python,Testing    # Filter by tags (must match ALL)
memory-query search --project=myproject              # All entries for project (no query, date-ordered)
memory-query search <query> --limit=50               # Default limit is 20
```

**Semantic search** — finds entries by meaning, not just keywords:
```bash
memory-query search-semantic "how to handle payment failures"
memory-query search-semantic "database schema" --project=mekanik
memory-query search-semantic "testing strategy" --tags=Python --limit=5
memory-query search-semantic "async pattern" --threshold=1.0  # Stricter matching
```

**Hybrid search** — combines FTS + semantic (the default you should reach for):
```bash
memory-query search-hybrid "Stripe webhook error handling"
memory-query search-hybrid "database migration" --project=abby-normal
memory-query search-hybrid "async pattern" --limit=10
```

Filter by project or tags works with all three search types.

### Search Details

**Keyword search** uses porter stemming — `connect` matches `connection`, `connected`, `connecting`. Results
are ordered by BM25 relevance. Each result includes:
- `excerpt`: match context with matched terms in `[brackets]`
- `bm25_score`: relevance score (more negative = more relevant)

Filter-only searches (no query) return results ordered by `created_at` with no `excerpt`.

**Semantic search** uses vector similarity (384-dim embeddings via all-MiniLM-L6-v2). Results include:
- `semantic_distance`: 0 = identical meaning, ~1.0 = typical match, >1.5 = unrelated

**Hybrid search** combines both: FTS finds exact keyword matches, semantic finds conceptual matches.
Entries found by both get a ranking boost. This is the search to use by default.

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

New entries are auto-embedded for semantic search. Skip with `--no-embed`:
```bash
memory-query add --title="Quick note" --content="..." --no-embed
```

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
- `memory_embeddings`: vec0 virtual table for vector similarity search (384-dim, all-MiniLM-L6-v2)
- `projects` and `components` tables: for filtering and organization
- Orchestration tables are separate (`orchestration_sessions`, `waves`, `agent_session`, etc.)

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

## Automatic Hooks (Preferred)

Both Claude Code and OpenCode now load memories automatically — no manual session-start search needed.

**Claude Code** (`~/.claude/settings.json`):
- `SessionStart` command hook runs `hooks/session_start.py`, which queries `search-hybrid <project>` and injects results as `additionalContext`
- `Stop` prompt hook nudges Claude to save learnings at turn end

**OpenCode** (`~/.config/opencode/plugins/abby-normal.js`):
- `experimental.chat.messages.transform` injects memories into the first user message of each session
- `experimental.session.compacting` re-injects at context compaction
- `abby_recall` and `abby_save` tools are available for explicit memory operations

**Project detection**: Both hooks derive the project ID from the working directory basename, mapped via `PROJECT_MAP` in each file. Project name is used as a boost term in hybrid search — not a hard filter — so cross-project memories surface when relevant.

If hooks aren't active (or you want to search manually):
```bash
memory-query search-hybrid <project-or-keyword>
```

## Key Architectural Decisions

**DEC-001**: Unified table over separate tables
Rationale: Agents don't know which table to query at runtime. One table is simpler.
Tags: Database, Architecture, SQLite

**DEC-002**: Untyped entries with optional tags
Rationale: Forced taxonomy (learning, pattern, decision, etc.) added friction without value. Entries are now just entries — tags are optional metadata for organization.
Tags: Database, Architecture, Simplification

**DEC-003**: CLI wrapper over raw SQL
Rationale: Agents struggle with SQL syntax. Python CLI scripts provide clean interface.
Tags: CLI, Python, Agent-UX

**DEC-004**: Skill-based over plugin-based orchestration
Rationale: Explicit control > magic automation. Agent consciously decides when to orchestrate.
Tags: OpenCode, Architecture, Skills

**DEC-005**: Hybrid search over keyword-only or semantic-only
Rationale: FTS5 provides exact keyword precision; semantic provides conceptual recall. Combined with weighted scoring and intersection bonuses, hybrid search surfaces the most relevant results from both approaches.
Tags: Search, Architecture, Semantic

**DEC-006**: Local embedding model over API-based
Rationale: Local-first philosophy. all-MiniLM-L6-v2 runs on CPU, no API key needed, no network dependency, no per-query cost. Aligns with abby-normal's SQLite-local architecture.
Tags: Search, Architecture, Semantic, Local-First

## Critical Learnings

**LEARN-001**: FTS search requires careful trigger setup
Virtual table + content table + triggers = working search. Easy to get wrong.

**LEARN-002**: JSON fields enable schema flexibility
Without rigid columns, we can store varying metadata per entry type. Trade-off: less validation.

**LEARN-003**: CLI commands must be discoverable
Agents need help text listing all available commands. Self-documenting CLI reduces errors.

**LEARN-004**: sqlite-vec requires pysqlite3 on some systems
Standard library sqlite3 may be compiled without load_extension support. pysqlite3-binary provides a drop-in replacement with extension loading.

**LEARN-005**: vec0 MATCH syntax, not equality
sqlite-vec queries use `WHERE embedding MATCH ?` not `WHERE embedding = ?`. The MATCH keyword triggers the vector similarity search.

## Conventions

- Tags are optional. Entries without tags are fully searchable via FTS and semantic search.
- Use `--project=` consistently — it's the primary grouping key across tools.
- Agents should never use raw SQL; always go through the CLI wrappers.
- The `memory-query` commands output JSON — pipe or parse accordingly.
- Use `search-hybrid` as your default search — it combines the best of FTS and semantic.

## Requirements

- Python 3.8+
- SQLite 3.25+ (for window functions)
- **For semantic search** (optional but recommended):
  - `pysqlite3-binary` — SQLite with extension loading
  - `sqlite-vec` — Vector similarity search extension
  - `sentence-transformers` — Local embedding model

Install all at once:
```bash
pip install pysqlite3-binary sqlite-vec sentence-transformers
```

## Personality

When appropriate, toss in a Young Frankenstein reference. Use sparingly.
