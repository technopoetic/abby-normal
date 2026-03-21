# abby-normal

A global memory system for AI agents with unified storage, full-text search, and multi-agent orchestration.

Named after the "Abby Normal" brain in Young Frankenstein.

## What It Does

abby-normal stores knowledge, decisions, and patterns from AI-assisted development sessions in a queryable SQLite database. It includes:

- **Unified memory**: Single table for all knowledge types with FTS search
- **Multi-agent orchestration**: Coordinate specialist agents with wave-based execution
- **Cross-project**: Search learnings across all your projects

## Quick Start

```bash
# Setup
cd ~/code/abby-normal
python3 setup.py          # Creates ~/.local/share/abby-normal/memory.db

# Create symlinks
ln -s ~/code/abby-normal/memory_query.py ~/.local/bin/memory-query
ln -s ~/code/abby-normal/orchestration.py ~/.local/bin/orchestration

# Add your projects
memory-query add --type=learning --title="..." --content="..." --project=myproject
```
memory-query project mekanik

# Add memory
memory-query add --type=learning --title="..." --content="..." --project=mekanik --tags=Python
```

## Database

Location: `~/.local/share/abby-normal/memory.db`

Schema: Unified `memory_entries` table with entry_type column:
- `learning` - Lessons learned
- `pattern` - Reusable solutions
- `decision` - Architectural/product decisions
- `pitfall` - Common mistakes to avoid
- `changelog` - Session history

## Multi-Agent Orchestration

*Optional extension. Originally from [this article](https://alirezarezvani.medium.com/97-of-developers-kill-their-claude-code-agents) about Claude Code orchestration.*

See `ORCHESTRATION_SETUP.md` for installation and configuration.

Switch to orchestrator agent (Tab key) or spawn:
```
@orchestrator implement user authentication
```

Coordinates specialist agents in waves with contract validation.

## Files

```
abby-normal/
├── setup.py              # Initialize database
├── schema.sql            # Database schema
├── memory_query.py       # Query CLI
├── orchestration.py      # Multi-agent coordination
└── AGENTS.md             # Detailed usage guide
```

## Requirements

- Python 3.8+
- SQLite 3.25+ (for window functions)

## Contributing

This is a personal project, but suggestions welcome via issues.

---

*"It's alive!"* — Young Frankenstein