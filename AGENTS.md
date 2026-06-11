# abby-normal — Global Memory System for AI Agents

*Named after the "Abby Normal" brain from Young Frankenstein.*

## What This Is

A SQLite-backed memory system for AI agents. Stores learnings, decisions, and patterns across projects with FTS search **and semantic vector search**.

## Setup

```bash
python3 ~/code/abby-normal/setup.py   # Creates ~/.local/share/abby-normal/memory.db

# Symlinks for CLI access
ln -s ~/code/abby-normal/memory_query.py ~/.local/bin/memory-query
ln -s ~/code/abby-normal/migrate_fts.py ~/.local/bin/migrate-abby-fts
```

Database lives at `~/.local/share/abby-normal/memory.db` — never delete it without explicit permission.

The database is **not** git-tracked. It's local-only data, machine-specific, and the historical snapshot at `~/.config/opencode/memory.db` is stale (kept as reference, not the live source). Back up manually if you want a snapshot.

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

**`search`** — the only command you need. Auto-selects:
- Hybrid (FTS5 + semantic) if sqlite-vec is available
- FTS-only if sqlite-vec is not available

```bash
memory-query search <query>                          # Default search
memory-query search <query> --project=myproject     # Filter by project
memory-query search <query> --tags=Python,Testing   # Filter by tags (must match ALL)
memory-query search --project=myproject             # All entries for project (no query, date-ordered)
memory-query search <query> --limit=50               # Default limit is 20
```

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

Results are ordered by BM25 relevance when a query is given. Each result includes:
- `excerpt`: match context with matched terms in `[brackets]`
- `bm25_score`: relevance score (more negative = more relevant)

Filter-only searches (no query) return results ordered by `created_at` with no `excerpt`.

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

## Automatic Hooks (Preferred)

Both Claude Code and OpenCode now load memories automatically — no manual session-start search needed.

**Claude Code** (`~/.claude/settings.json`):
- `SessionStart` command hook runs `hooks/session_start.py`, which queries `search-hybrid <project>` and injects results as `additionalContext`
- `Stop` prompt hook requires Claude to run `memory-query search` first, then default-deny save (see LEARN-009)

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

**LEARN-006**: HuggingFace Hub warnings are silenced in embeddings.py
`get_model()` captures both Python warnings and stderr (tqdm progress bars) during model load via `warnings.catch_warnings` + `contextlib.redirect_stderr`, routing them to `logging.debug`. To skip HF update checks entirely, set `HF_HUB_OFFLINE=1` in your environment.

**LEARN-007**: Venv re-invocation uses `__file__` + `sys.argv[1:]`
Both `memory_query.py` and `backfill_embeddings.py` re-invoke themselves under the venv Python using `[venv_python, __file__] + sys.argv[1:]`. Using `sys.argv` directly (which includes `sys.argv[0]`) triggers a semgrep `dangerous-subprocess-use-tainted-env-args` finding. `__file__` is the correct, fixed script path.

**LEARN-008**: pysqlite3-binary unavailable on macOS arm64 + Python 3.12
`pysqlite3-binary` has no wheels for this platform. However, stdlib `sqlite3` (via mise-installed Python) supports `load_extension`, making `pysqlite3` unnecessary. Both `embeddings.py` and `memory_query.py` now try pysqlite3 first, fall back to stdlib sqlite3. Linux behavior unchanged.

**LEARN-009**: Stop-prompt "save memories" nudges cause noise
Claude treated the old Stop hook ("If there are new learnings worth keeping, save them... respond OK") as a save-instruction, not a nudge — it saved filler entries every session. Fixed by rewriting the prompt to lead with "DEFAULT: do nothing", require `memory-query search` first to dedupe, and bake the same three-criteria bar into the OpenCode `abby_save` tool description (the model reads the tool description at every call). See `~/.claude/settings.json` Stop hook and `hooks/abby-normal.js` for current wording.

## Conventions

- Tags are optional. Entries without tags are fully searchable via FTS and semantic search.
- Use `--project=` consistently — it's the primary grouping key across tools.
- Agents should never use raw SQL; always go through the CLI wrappers.
- The `memory-query` commands output JSON — pipe or parse accordingly.
- Use `search` as your default — it auto-selects hybrid or FTS-only based on availability.
- For agent guidance on when to use memory-query: `memory-query --agent`

## Requirements

- Python 3.8+
- SQLite 3.25+ (for window functions)
- **For semantic search** (optional but recommended):
  - `sqlite-vec` — Vector similarity search extension
  - `sentence-transformers` — Local embedding model
  - `pysqlite3-binary` — Only needed on Linux where stdlib sqlite3 may lack `load_extension`

Install with uv (preferred):
```bash
uv sync                    # macOS (stdlib sqlite3 supports load_extension)
uv sync --extra linux      # Linux (includes pysqlite3-binary)
```

## Personality

When appropriate, toss in a Young Frankenstein reference. Use sparingly.
