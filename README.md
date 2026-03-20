# abby-normal — Global Memory System for AI Agents

*Named after the "Abby Normal" brain in Young Frankenstein*

A centralized SQLite-based memory system with unified storage, full-text search, and multi-agent orchestration.

## Overview

abby-normal stores project history, decisions, patterns, and learnings in a single queryable database at `~/.config/opencode/memory.db`. It features:

- **Unified memory**: Single `memory_entries` table for all knowledge types
- **Full-text search**: FTS5 for fast natural language queries
- **Multi-agent orchestration**: Wave-based coordination with contract validation
- **Cross-project**: Search memory across all your projects

## Quick Start

### Query Memory

```bash
# Search everything
memory-query search authentication
memory-query search "unified table"

# Filter by project
memory-query search --project=mekanik testing
memory-query search --project=abby-normal

# Filter by type
memory-query search --type=decision
memory-query search --type=pattern --tags=Python

# Filter by tags
memory-query search --tags=Python,Testing
```

### Get Project Info

```bash
memory-query project mekanik
memory-query project abby-normal
memory-query active-projects
```

### Add Memory

```bash
memory-query add \
  --type=learning \
  --title="Never use raw SQL" \
  --content="Agents struggle with SQL. Use CLI wrappers instead." \
  --project=mekanik \
  --tags=Python,Agent-UX
```

**Entry Types**: `learning`, `pattern`, `decision`, `pitfall`, `changelog`

## Database Schema

### Unified Memory (memory_entries)

All knowledge stored in one flexible table:

```sql
memory_entries (
    id TEXT PRIMARY KEY,              -- LEARN-20260320-123456-abc123
    entry_type TEXT NOT NULL,         -- learning, pattern, decision, pitfall
    project_id TEXT,                  -- mekanik, abby-normal, etc.
    component_name TEXT,              -- Backend, Frontend, etc.
    title TEXT NOT NULL,              -- Short title
    content TEXT NOT NULL,            -- Full content
    metadata JSON,                    -- Flexible: author, rationale, etc.
    tags JSON,                        -- ["Python", "Testing"]
    created_at TIMESTAMP
)
```

### Projects & Components

```sql
projects (id, name, full_name, status, current_phase)
components (id, project_id, name, repository, tech_stack)
```

### Orchestration Tables (Multi-Agent)

```sql
orchestration_sessions -- Multi-agent run tracking
waves                  -- Parallel agent batches
agent_sessions         -- Individual agent runs
interface_contracts    -- Extracted type contracts
contract_mismatches    -- Validation failures
```

## CLI Commands

### memory-query

```bash
# Search
memory-query search <query> [--type=X] [--project=Y] [--tags=a,b]

# Add
memory-query add --type=X --title=Y --content=Z [--project=A] [--tags=b,c]

# Project info
memory-query project <project_id>
memory-query active-projects
memory-query vocabulary [--category=X]
```

### orchestration

```bash
# Create session
orchestration create-session <project_id> "<description>" [--max-agents=N]

# Create wave
orchestration create-wave <session_id> <wave_number>

# Add agent
orchestration create-agent <session_id> <wave_id> <name> <type> "<task>"

# Validate contracts
orchestration validate-wave <wave_id> <session_id> <project_id>

# Query state
orchestration get-wave-agents <wave_id>
orchestration get-mismatches <wave_id>
orchestration get-contracts <wave_id>
```

## Multi-Agent Orchestration

### Concept

Break complex tasks into **waves** of parallel agents:

```
Wave 1: Foundation
  - Database schema
  - API types
  
Wave 2: Implementation
  - Backend API
  - Frontend components
  
Wave 3: Integration
  - Tests
  - Documentation
```

Each wave validates contracts before proceeding to the next.

### Usage

Switch to orchestrator agent (Tab key) or spawn:
```
@orchestrator implement user authentication
```

The orchestrator:
1. Creates waves based on dependencies
2. Spawns specialist agents in parallel
3. Validates interface contracts
4. Auto-fixes mismatches
5. Synthesizes results

See `~/.config/opencode/skills/orchestration/SKILL.md` for full workflow.

## Session Workflow

### At Session Start

Query relevant memory:
```bash
memory-query search --project=mekanik "current phase"
memory-query search --type=decision --tags=Architecture
```

### During Session

Reference as needed:
```bash
memory-query search "stripe webhook"
```

### At Session End

Add learnings:
```bash
memory-query add \
  --type=learning \
  --title="Discovered edge case with webhooks" \
  --content="Webhooks can arrive out of order..." \
  --project=mekanik \
  --tags=Stripe,Webhooks,Critical
```

## Python API

```python
from memory_query import MemoryQuery

with MemoryQuery() as mq:
    # Search
    results = mq.search_memory(
        query="authentication",
        project_id="mekanik",
        tags=["Python"]
    )
    
    # Add entry
    mq.add_memory_entry(
        entry_id="LEARN-001",
        entry_type="learning",
        title="...",
        content="...",
        project_id="mekanik",
        tags=["Python", "Testing"]
    )
```

## Git Workflow

The database is version controlled:

```bash
cd ~/.config/opencode
git add memory.db
git commit -m "Session 7: Added auth learnings"
```

**Never delete memory.db** without explicit permission.

## Troubleshooting

### Database locked
Close all Python processes accessing memory.db.

### FTS not finding results
Rebuild indexes:
```bash
sqlite3 ~/.config/opencode/memory.db "INSERT INTO memory_entries_fts(memory_entries_fts) VALUES('rebuild');"
```

### Hyphens in search
Wrap queries with special characters in quotes:
```bash
memory-query search "abby-normal"
```

## Files

```
abby-normal/
├── AGENTS.md              # Project-specific documentation
├── schema.sql             # Database schema (v2.0)
├── memory_query.py        # Query CLI tool
├── orchestration.py       # Multi-agent orchestration
├── seed_database.py       # Initial data seeding
├── migrate_*.py           # Migration from PROJECT-MEMORY.json
├── memory_export.py       # Export to JSON
└── README.md              # This file

~/.config/opencode/memory.db  # Database (git-tracked)
```

## Architecture Decisions

**Unified Table**: Single `memory_entries` instead of separate learnings/patterns/decisions tables. Agents don't know which table to query at runtime.

**CLI Over SQL**: Python wrappers for all database operations. Agents call CLI instead of writing SQL.

**Skill Over Plugin**: Explicit skill-based orchestration vs automatic plugin. Agent consciously decides when to coordinate.

---

**Version**: 2.0.0  
**Location**: `~/code/abby-normal`  
**Maintainer**: Richard Hibbitts  
**Inspiration**: *Young Frankenstein* — "Abby Normal" brain in a jar