# abby-normal: Remove entry_type — Simplify to Untyped Memory

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the `entry_type` forced taxonomy from abby-normal. Entries are just... entries. Tags provide optional categorization.

**Architecture:** The unified `memory_entries` table already stores title, content, metadata JSON, and tags. The `entry_type` column was a forced taxonomy that added friction without value. Removing it simplifies the schema while preserving search and optional tagging. The FTS index on title+content remains the primary discovery mechanism.

**Tech Stack:** Python 3.8+, SQLite 3.25+ (FTS5)

---

## Task 1: Update schema.sql — Remove entry_type column

**Files:**
- Modify: `schema.sql:37-48` (memory_entries table)
- Modify: `schema.sql:76` (index removal)

**Step 1: Remove entry_type column and update memory_entries table**

Replace lines 37-48:
```sql
CREATE TABLE IF NOT EXISTS memory_entries (
    id TEXT PRIMARY KEY,
    project_id TEXT,                    -- NULL for global entries
    component_name TEXT,                -- NULL for project-wide
    title TEXT NOT NULL,
    content TEXT NOT NULL,              -- Full text content
    metadata JSON,                      -- Flexible: author, rationale, outcome, tags, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

**Step 2: Remove idx_memory_type index**

Remove line 76:
```sql
CREATE INDEX IF NOT EXISTS idx_memory_type ON memory_entries(entry_type);
```

**Step 3: Commit**

```bash
git add schema.sql
git commit -m "feat: remove entry_type column - entries are now untyped"
```

---

## Task 2: Update memory_query.py — Remove entry_type from class methods

**Files:**
- Modify: `memory_query.py:65-127` (search_memory method)
- Modify: `memory_query.py:129-170` (add_memory_entry method)

**Step 1: Update search_memory method signature and implementation**

Replace `search_memory` method (lines 65-127) with:
```python
def search_memory(
    self,
    query: Optional[str] = None,
    project_id: Optional[str] = None,
    component_name: Optional[str] = None,
    tags: Optional[List[str]] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Search memory entries with optional filters.
    
    Args:
        query: Full-text search query
        project_id: Filter by project
        component_name: Filter by component
        tags: Filter by tags (must have ALL specified tags)
        limit: Max results to return
    """
    sql = "SELECT m.* FROM memory_entries m"
    where_clauses = []
    params = []

    # FTS search - escape special characters by wrapping in quotes
    if query:
        sql += " JOIN memory_entries_fts fts ON m.rowid = fts.rowid"
        where_clauses.append("memory_entries_fts MATCH ?")
        escaped_query = f'"{query}"'
        params.append(escaped_query)

    # Project filter
    if project_id:
        where_clauses.append("m.project_id = ?")
        params.append(project_id)

    # Component filter
    if component_name:
        where_clauses.append("m.component_name = ?")
        params.append(component_name)

    # Tag filters (must match ALL tags)
    if tags:
        for tag in tags:
            where_clauses.append("json_extract(m.tags, '$') LIKE ?")
            params.append(f'%"{tag}"%')

    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)

    sql += " ORDER BY m.created_at DESC LIMIT ?"
    params.append(limit)

    cursor = self.conn.execute(sql, params)
    return self._rows_to_dicts(cursor.fetchall())
```

**Step 2: Update add_memory_entry method signature and implementation**

Replace `add_memory_entry` method (lines 129-170) with:
```python
def add_memory_entry(
    self,
    entry_id: str,
    title: str,
    content: str,
    project_id: Optional[str] = None,
    component_name: Optional[str] = None,
    metadata: Optional[Dict] = None,
    tags: Optional[List[str]] = None,
) -> None:
    """
    Add a new memory entry.
    
    Args:
        entry_id: Unique ID (e.g., 'MEM-20260320-123456-abc123')
        title: Short title
        content: Full content/description
        project_id: Associated project (optional)
        component_name: Associated component (optional)
        metadata: Flexible JSON metadata (can include 'type', 'author', etc.)
        tags: List of tags for optional categorization
    """
    self.conn.execute(
        """
        INSERT INTO memory_entries 
        (id, project_id, component_name, title, content, metadata, tags)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry_id,
            project_id,
            component_name,
            title,
            content,
            json.dumps(metadata) if metadata else None,
            json.dumps(tags) if tags else None,
        ),
    )
    self.conn.commit()
```

**Step 3: Commit**

```bash
git add memory_query.py
git commit -m "feat: remove entry_type from MemoryQuery class"
```

---

## Task 3: Update memory_query.py CLI — Remove --type from add and search

**Files:**
- Modify: `memory_query.py:197-319` (main CLI function)

**Step 1: Update CLI help text and add command validation**

Replace the `main()` function's add command section (around line 270) to remove entry_type:

Change:
```python
if not entry_type or not title or not content:
    print("Error: --type, --title, and --content are required")
    sys.exit(1)
```
To:
```python
if not title or not content:
    print("Error: --title and --content are required")
    sys.exit(1)
```

And change the entry_id generation from:
```python
# Determine prefix based on type
prefix = entry_type.upper()[:5]
entry_id = f"{prefix}-{timestamp}-{suffix}"
```
To:
```python
entry_id = f"MEM-{timestamp}-{suffix}"
```

**Step 2: Remove --type parsing from both search and add commands**

In the search command parsing (around line 223), remove:
```python
elif arg.startswith("--type="):
    entry_type = arg.split("=", 1)[1]
```

In the add command parsing (around line 254), remove:
```python
elif arg.startswith("--type="):
    entry_type = arg.split("=", 1)[1]
```

And update the search call to remove `entry_type` parameter.

**Step 3: Update help text**

Update lines 200-206 to remove --type references:
```python
print("Usage: memory_query.py <command> [args...]")
print("Commands:")
print("  search <query> [--project=Y] [--tags=a,b,c] [--limit=N]")
print("  add --title=Y --content=Z [--project=A] [--component=B] [--tags=c,d] [--metadata=JSON]")
print("  project <project_id>")
print("  active-projects")
print("  vocabulary [--category=X]")
```

**Step 4: Commit**

```bash
git add memory_query.py
git commit -m "feat: remove --type from CLI interface"
```

---

## Task 4: Update migrate_mekanik_data.py — Remove entry_type from migration

**Files:**
- Modify: `migrate_mekanik_data.py` (all functions)

**Step 1: Update INSERT statements to remove entry_type column**

In all four INSERT statements (migrate_learnings, migrate_decisions, migrate_architectural_decisions, migrate_changelog), change:
```sql
INSERT INTO memory_entries 
(id, entry_type, project_id, component_name, title, content, metadata, tags)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
```
To:
```sql
INSERT INTO memory_entries 
(id, project_id, component_name, title, content, metadata, tags)
VALUES (?, ?, ?, ?, ?, ?, ?)
```

And remove the entry_type value from the VALUES tuple.

**Step 2: Update function signatures to not pass entry_type**

Remove `entry_type` parameter from all INSERT calls.

**Step 3: Commit**

```bash
git add migrate_mekanik_data.py
git commit -m "feat: remove entry_type from mekanik migration"
```

---

## Task 5: Update AGENTS.md and README.md — Document simplified approach

**Files:**
- Modify: `AGENTS.md:85-86, 89-91, 153-159`
- Modify: `README.md` (same section)

**Step 1: Update AGENTS.md**

Remove all references to entry_type as a required/forced concept. Update documentation to show that entries are untyped, and tags are optional.

Key sections to update:
- Line 85-86: Remove entry_type from "Entry Types" list
- Line 89-91: Update memory_entries schema description
- Line 153-159: Update commands reference

**Step 2: Update README.md similarly**

**Step 3: Commit**

```bash
git add AGENTS.md README.md
git commit -m "docs: update documentation for untyped entries"
```

---

## Task 6: Test the changes

**Files:**
- Test: `~/.local/share/abby-normal/memory.db` (existing database)

**Step 1: Verify schema change works**

Check if the database needs recreation or if we can ALTER TABLE:

```bash
sqlite3 ~/.local/share/abby-normal/memory.db ".schema memory_entries"
```

If schema has old entry_type column, we'll need to either:
- Recreate database (backup first)
- Or run ALTER TABLE to drop column (SQLite supports this in 3.35.0+)

**Step 2: Run a test add**

```bash
cd ~/code/abby-normal
python3 -c "
from memory_query import MemoryQuery
mq = MemoryQuery()
import random, string
suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
mq.add_memory_entry(
    entry_id=f'TEST-{suffix}',
    title='Test entry: untyped memory works',
    content='If you can read this, entry_type removal succeeded.',
    project_id='abby-normal',
    tags=['testing', 'untyped']
)
print('Entry added successfully')
"
```

**Step 3: Run a test search**

```bash
memory-query search "untyped memory"
```

Expected: Should find the test entry

**Step 4: Clean up test entry**

```bash
memory-query search "untyped memory" | python3 -c "import sys,json; entries=json.load(sys.stdin); [print(e['id']) for e in entries]" | xargs -I {} sqlite3 ~/.local/share/abby-normal/memory.db "DELETE FROM memory_entries WHERE id='{}'"
```

**Step 5: Commit**

```bash
git add -A
git commit -m "test: verify untyped entries work correctly"
```

---

## Task 7: Migrate existing PROJECT-MEMORY.json files to new schema

**Files:**
- Create: `migrate_to_untyped.py` (new migration script)
- Run: Against mekanik and trackstack

**Step 1: Create migration script for existing data**

Create `migrate_to_untyped.py`:
```python
#!/usr/bin/env python3
"""Migrate existing entries from typed (entry_type column) to untyped schema."""

import sqlite3
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    
    # Check if entry_type column exists
    cursor = conn.execute("PRAGMA table_info(memory_entries)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'entry_type' not in columns:
        print("✓ Database already uses untyped schema")
        conn.close()
        return
    
    # Migrate entry_type to metadata.tags if not already there
    cursor = conn.execute("SELECT id, entry_type, metadata, tags FROM memory_entries")
    rows = cursor.fetchall()
    
    for row in rows:
        entry_id, entry_type, metadata, tags = row
        
        # Parse existing JSON fields
        import json
        meta = json.loads(metadata) if metadata else {}
        tag_list = json.loads(tags) if tags else []
        
        # Add entry_type as a tag if it exists and isn't already a tag
        if entry_type and entry_type not in tag_list:
            tag_list.append(entry_type)
        
        # Update entry
        conn.execute("""
            UPDATE memory_entries 
            SET metadata = ?, tags = ?
            WHERE id = ?
        """, (json.dumps(meta), json.dumps(tag_list), entry_id))
    
    # Note: We keep entry_type column but don't use it
    # SQLite doesn't easily drop columns, so we just stop using it
    
    conn.commit()
    print("✓ Migrated entry_type values to tags")
    conn.close()

if __name__ == "__main__":
    migrate()
```

**Step 2: Run migration**

```bash
python3 migrate_to_untyped.py
```

**Step 3: Verify data**

```bash
memory-query search --project=mekanik | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Found {len(d)} entries'); [print(f'  - {e[\"title\"][:50]}') for e in d[:5]]"
```

**Step 4: Commit migration script**

```bash
git add migrate_to_untyped.py
git commit -m "feat: add migration script for untyped entries"
```

---

## Task 8: Migrate PROJECT-MEMORY.json files from mekanik and trackstack

**Files:**
- Run: `migrate_mekanik_data.py` (updated in Task 4)
- Create: Similar script for trackstack if needed

**Step 1: Verify migrate_mekanik_data.py works with new schema**

Check that the script runs without entry_type errors.

**Step 2: Run migration for mekanik canonical file**

The canonical file is: `/home/rhibbitts/code/python/mekanik/PROJECT-MEMORY.json`

Update the path in migrate_mekanik_data.py or create a wrapper.

**Step 3: Run migration for trackstack**

Create `migrate_trackstack_data.py` based on mekanik structure.

**Step 4: Verify migrated data**

```bash
memory-query search --project=mekanik | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'mekanik: {len(d)} entries')"
memory-query search --project=trackstack | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'trackstack: {len(d)} entries')"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `schema.sql` | Remove `entry_type` column and `idx_memory_type` index |
| `memory_query.py` | Remove `entry_type` param from `search_memory()` and `add_memory_entry()`; update CLI |
| `migrate_mekanik_data.py` | Remove `entry_type` from INSERT statements |
| `AGENTS.md` | Remove entry_type documentation |
| `README.md` | Remove entry_type documentation |
| `migrate_to_untyped.py` | New: Migrate existing entries to tags |
| `migrate_trackstack_data.py` | New: Migrate trackstack PROJECT-MEMORY.json |

---

## Verification Commands

After all tasks:
```bash
# Search should work without --type
memory-query search "subscription"
memory-query search --project=mekanik

# Add should work without --type
memory-query add --title="Test" --content="Testing untyped add"

# Help should not mention --type
memory-query
```

---

## Execution Options

**Plan complete and saved.** Two execution options:

**1. Subagent-Driven (this session)** - I dispatch fresh subagent per task, review between tasks, fast iteration

**2. Parallel Session (separate)** - Open new session with executing-plans, batch execution with checkpoints

**Which approach?**
