# abby-normal — Global Memory System for AI Agents

*From Young Frankenstein: "Abby Normal" — the brain in a jar*

## Current State

**Status**: Core Implementation Complete (v2.0)  
**Phase**: Active — Testing and Documentation  
**Location**: `/home/rhibbitts/code/abby-normal`  

**What's Working**:
- Unified `memory_entries` table with FTS search
- CLI tools: `memory-query`, `orchestration`
- Schema v2.0 (simplified from multiple tables)
- Cross-project memory storage and retrieval
- Orchestration system for multi-agent coordination

## How to Use abby-normal

### Query Memory (At Session Start)

Search across all memory types:
```bash
memory-query search <keyword>
memory-query search authentication
memory-query search "unified table"
```

Filter by project:
```bash
memory-query search --project=mekanik
memory-query search --project=abby-normal testing
```

Filter by type:
```bash
memory-query search --type=decision
memory-query search --type=pattern --tags=Python
```

Filter by tags:
```bash
memory-query search --tags=Python,Testing
memory-query search --project=mekanik --tags=API
```

Get project details:
```bash
memory-query project mekanik
memory-query project abby-normal
```

### Add Memory (At Session End)

Add a learning:
```bash
memory-query add \
  --type=learning \
  --title="Never use raw SQL in agents" \
  --content="Agents struggle with SQL syntax. Always use CLI wrappers." \
  --project=abby-normal \
  --tags=Agent-UX,CLI
```

Add a decision:
```bash
memory-query add \
  --type=decision \
  --title="Use SQLite over PostgreSQL for local-first" \
  --content="SQLite requires no server setup, perfect for local agent memory." \
  --project=abby-normal \
  --tags=Database,Architecture
```

Add a pattern:
```bash
memory-query add \
  --type=pattern \
  --title="Unified table with JSON metadata" \
  --content="Single table + entry_type column + flexible JSON metadata = query simplicity." \
  --project=abby-normal \
  --tags=Database,Pattern
```

**Entry Types**: `learning`, `pattern`, `decision`, `pitfall`, `changelog`

## Database Schema

### memory_entries (Unified Memory)
- `id`: Unique identifier (e.g., LEARN-20260320-123456-abc123)
- `entry_type`: learning, pattern, decision, pitfall, changelog
- `project_id`: Associated project (NULL for global)
- `component_name`: Component within project (NULL for project-wide)
- `title`: Short title
- `content`: Full text content
- `metadata`: JSON with flexible fields
- `tags`: JSON array of tags
- `created_at`: Timestamp

### projects & components
- Track project metadata and repository locations
- Used for filtering and organization

### Orchestration Tables (Separate System)
- `orchestration_sessions`: Multi-agent runs
- `waves`: Parallel agent batches
- `agent_sessions`: Individual agent tracking
- `interface_contracts`: Extracted type contracts
- `contract_mismatches`: Validation failures

## Key Architectural Decisions

**DEC-001**: Unified table over separate tables  
Rationale: Agents don't know which table to query at runtime. One table + entry_type is simpler.  
Tags: Database, Architecture, SQLite

**DEC-002**: CLI wrapper over raw SQL  
Rationale: Agents struggle with SQL syntax. Python CLI scripts provide clean interface.  
Tags: CLI, Python, Agent-UX

**DEC-003**: Skill-based over plugin-based orchestration  
Rationale: Explicit control > magic automation. Agent consciously decides when to orchestrate.  
Tags: OpenCode, Architecture, Skills

## Critical Learnings

**LEARN-001**: FTS search requires careful trigger setup  
Virtual table + content table + triggers = working search. Easy to get wrong.

**LEARN-002**: JSON fields enable schema flexibility  
Without rigid columns, we can store varying metadata per entry type. Trade-off: less validation.

**LEARN-003**: CLI commands must be discoverable  
Agents need help text listing all available commands. Self-documenting CLI reduces errors.

## File Structure

```
abby-normal/
├── schema.sql              # Database schema
├── memory_query.py         # Query CLI tool
├── orchestration.py        # Orchestration CLI tool
├── memory_export.py        # Export to JSON
└── README.md               # Documentation

~/.local/share/abby-normal/memory.db  # Actual database
```

## Commands Reference

```bash
# Query
memory-query search <query> [--type=X] [--project=Y] [--tags=a,b]
memory-query project <project_id>
memory-query active-projects
memory-query vocabulary [--category=X]

# Add
memory-query add --type=X --title=Y --content=Z [--project=A] [--tags=b,c]

# Orchestration (if using multi-agent features)
orchestration create-session <project_id> "<description>" [--max-agents=N]
orchestration create-wave <session_id> <wave_number>
orchestration create-agent <session_id> <wave_id> <name> <type> "<task>"
orchestration validate-wave <wave_id> <session_id> <project_id>
```

## Workflow

1. **Start Session**: Query relevant memory
   ```bash
   memory-query search --project=abby-normal "current phase"
   memory-query search --type=decision --tags=Architecture
   ```

2. **During Session**: Reference as needed
   ```bash
   memory-query search "unified table"
   ```

3. **End Session**: Add new learnings/decisions
   ```bash
   memory-query add --type=learning --title="..." --content="..." --project=abby-normal --tags=...
   ```

## Integration with Other Projects

abby-normal stores memory for all projects. Each project has:
- Entry in `projects` table
- Components in `components` table
- Memory entries tagged with `project_id`

Query cross-project:
```bash
memory-query search "testing pattern"  # Searches all projects
memory-query search --project=mekanik testing  # Specific project
```

## Git Workflow

Database is at `~/.local/share/abby-normal/memory.db` and is git-tracked:
```bash
cd ~/.config/opencode
git add memory.db
git commit -m "Session N: Added learnings about X"
```

**Never delete memory.db** without explicit permission.

## Testing

Test queries:
```bash
memory-query search test
memory-query project abby-normal
memory-query search --type=learning --project=abby-normal
```

Verify FTS works:
```bash
memory-query search "unified table beats separate"
```

## Next Steps

- [ ] Plugin for automatic session-start loading (optional)
- [ ] Migration from PROJECT-MEMORY.json for mekanik/lora
- [ ] Enhanced tagging/tag suggestion
- [ ] Memory compaction/archival for old entries

---

## Personality

**Young Frankenstein References**

abby-normal is named after the "Abby Normal" brain from Young Frankenstein. When appropriate and relevant, toss in a Young Frankenstein quote or reference:

- **"It's alive!"** — When something works for the first time
- **"Abby... Normal"** — When discussing the name or brain references
- **"Destiny! Destiny! No escaping that for me!"** — When discussing fate or inevitability
- **"Could be worse, could be raining"** — When things go wrong (classic Igor line)
- **"What hump?"** — When someone mentions a problem that seems obvious to you
- **"Walk this way"** — When giving instructions (with Igor's limp implied)

Use sparingly — only when it adds humor without being distracting. Keep it professional, just with a touch of Mel Brooks whimsy.

---

**Note**: This AGENTS.md file is for the abby-normal project itself. Use `memory-query` commands above to interact with the system.