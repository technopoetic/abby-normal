# Multi-Agent Orchestration Setup

*Optional extension for abby-normal. Adapted from ["97% of developers kill their Claude Code agents"](https://alirezarezvani.medium.com/97-of-developers-kill-their-claude-code-agents-in-the-first-10-minutes-heres-how-the-3-build-d2b6913f4cb2) by Alireza Rezvani.*

## Overview

This adds wave-based multi-agent coordination to abby-normal, allowing the orchestrator agent to coordinate specialist agents for complex tasks.

## Prerequisites

1. abby-normal installed and working
2. OpenCode with agent support
3. Access to `~/.config/opencode/` directory

## Installation

### 1. Create Agent Directory

```bash
mkdir -p ~/.config/opencode/agents
```

### 2. Copy Agent Configurations

```bash
cp ~/code/abby-normal/agents/*.md ~/.config/opencode/agents/
```

This installs: `orchestrator`, `backend-specialist`, `frontend-specialist`, `contract-fix`, plus review agents (`review-backend`, `review-devops`, `review-frontend`, `review-lead`).

The canonical agent definitions live in `~/code/abby-normal/agents/`. Edit them there and re-run the `cp` to update.

## Testing

1. **Verify agents are loaded**
   ```bash
   ls ~/.config/opencode/agents/
   # Should show: orchestrator.md backend-specialist.md frontend-specialist.md contract-fix.md
   ```

2. **Test orchestrator agent**
   - Press `Tab` in OpenCode to cycle agents
   - Should see "Orchestrator" option

## Usage

**Option 1: Switch to Orchestrator**
```
Press Tab → Select "Orchestrator"
Add user authentication to the app
```

**Option 2: Spawn Orchestrator**
```
@orchestrator add user authentication to the app
```

The orchestrator will:
1. Analyze the request
2. Create waves
3. Spawn specialist agents
4. Validate contracts
5. Synthesize results

## Troubleshooting

**Agent not appearing**: Check file permissions on .md files
```bash
chmod 644 ~/.config/opencode/agents/*.md
```

**Contracts not validating**: Check `orchestration.py` is in PATH and database is accessible

## Architecture

The orchestration system uses abby-normal's database for state:
- `orchestration_sessions` — Multi-agent runs
- `waves` — Parallel agent batches
- `agent_sessions` — Individual agent tracking
- `interface_contracts` — Extracted type contracts
- `contract_mismatches` — Validation failures

All orchestration state is stored alongside your project memory.

---

*Original concept from Alireza Rezvani's article on Claude Code orchestration. Adapted for OpenCode and abby-normal.*