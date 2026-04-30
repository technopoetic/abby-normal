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

# Search (keyword)
memory-query search authentication

# Search (semantic — finds entries about login, OAuth, session tokens too)
memory-query search-semantic "how to handle user authentication"

# Search (hybrid — best of both)
memory-query search-hybrid "Stripe webhook error handling"

# Add memory
memory-query add --title="..." --content="..." --project=myproject --tags=Python
```

## Search Types

| Type | How it works | Best for |
|------|-------------|----------|
| `search` | FTS5 keyword matching | Exact terms, proper nouns, specific words |
| `search-semantic` | Vector similarity (384-dim embeddings) | Conceptual matches, different words same meaning |
| `search-hybrid` | FTS5 + semantic combined | General queries — the default you should reach for |

Example: `search-hybrid "payment failure handling"` finds:
- Entries containing "payment" or "failure" (FTS5)
- Entries about "Stripe webhook errors", "credit card retry logic" (semantic)
- Entries found by **both** get a ranking boost (hybrid bonus)

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
└── README.md               # This file
```

## Contributing

This is a personal project, but suggestions welcome via issues.

---

*"It's alive!"* — Young Frankenstein
