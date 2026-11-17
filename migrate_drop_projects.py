#!/usr/bin/env python3
"""
One-time migration: drop the projects/components tables and the
memory_entries.component_name column, fold mekanik_* project ids into mekanik,
and add directory aliases so the split doesn't recur. Also drops the empty
tables left behind by the removed orchestration layer.

Why:
- Nothing in the code ever wrote to `projects`, so `active-projects` showed
  4 hand-seeded rows while entries use 37 project ids. Project listing is now
  derived from memory_entries instead.
- `components` was used by 3 of ~509 entries and never exposed to search.
  Those values are preserved as tags.
- memory_entries declared FOREIGN KEY ... REFERENCES projects ON DELETE CASCADE.
  Dropping `projects` with foreign_keys enabled would cascade-delete entries,
  and leaving the FK dangling breaks inserts if FKs are ever enabled. So the
  table is rebuilt without it.

memory_entries has a TEXT primary key, so its rowid is implicit. FTS and the
vec0 embeddings are keyed by rowid, so the rebuild copies rowids explicitly
and the script verifies the rowid->id mapping is unchanged.

Usage:
    python3 migrate_drop_projects.py [--db=PATH] [--dry-run]

--dry-run performs the whole migration inside a transaction, verifies it,
then rolls back.
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"

# Old project_id -> (new project_id, tag recording where it came from)
PROJECT_FOLDS = {
    "mekanik_vue": ("mekanik", "frontend"),
    "mekanik_docs": ("mekanik", "docs"),
    "mekanik_registration": ("mekanik", "registration"),
}

# Directory basenames -> project. mekanik_docs was the dirname on another
# machine; mekanik-docs is the dirname on this one.
ALIASES = {
    "mekanik_vue": "mekanik",
    "mekanik_docs": "mekanik",
    "mekanik-docs": "mekanik",
    "mekanik_registration": "mekanik",
}


# Left behind by the orchestration layer removed in 43036be, plus
# project_languages. Two of them carry foreign keys to `projects`.
DEAD_TABLES = [
    "agent_sessions",
    "contract_mismatches",
    "interface_contracts",
    "orchestration_sessions",
    "synthesis_results",
    "task_dependencies",
    "waves",
    "project_languages",
]


def _add_tag(metadata_json, tag):
    metadata = json.loads(metadata_json) if metadata_json else {}
    tags = metadata.get("tags") or []
    if tag not in tags:
        tags.append(tag)
    metadata["tags"] = tags
    return json.dumps(metadata)


def migrate(conn, dry_run):
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    columns = {r[1] for r in conn.execute("PRAGMA table_info(memory_entries)")}
    needs_rebuild = "projects" in tables or "component_name" in columns
    dead_present = [t for t in DEAD_TABLES if t in tables]
    if not needs_rebuild and not dead_present:
        print("Already migrated; nothing to do.")
        return

    # Must be set outside a transaction. Belt-and-braces: nothing enables it
    # today, but a cascade here would delete entries.
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN")

    if needs_rebuild:
        _rebuild(conn)
    else:
        print("Projects/components already removed; skipping rebuild.")
    _drop_dead_tables(conn, dead_present)

    if dry_run:
        conn.execute("ROLLBACK")
        print("Dry run: rolled back.")
    else:
        conn.execute("COMMIT")
        print("Committed.")


def _drop_dead_tables(conn, dead_present):
    # Refuse rather than drop anything holding data: these are expected to be
    # empty, and a non-empty one means something still uses it.
    for table in dead_present:
        rows = conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        if rows:
            raise RuntimeError(f"{table} has {rows} rows; not dropping it. Rolling back.")
    for table in dead_present:
        conn.execute(f"DROP TABLE {table}")
    print(f"Dropped empty leftover tables: {len(dead_present)}")


def _rebuild(conn):
    before = dict(conn.execute("SELECT rowid, id FROM memory_entries").fetchall())
    print(f"Entries before: {len(before)}")

    # 1. Fold component_name into tags.
    rows = conn.execute(
        "SELECT rowid, component_name, metadata FROM memory_entries "
        "WHERE component_name IS NOT NULL AND component_name <> ''"
    ).fetchall()
    for rowid, component, metadata in rows:
        conn.execute(
            "UPDATE memory_entries SET metadata = ? WHERE rowid = ?",
            (_add_tag(metadata, component.lower()), rowid),
        )
    print(f"Component values moved to tags: {len(rows)}")

    # 2. Fold mekanik_* project ids.
    for old, (new, tag) in PROJECT_FOLDS.items():
        rows = conn.execute(
            "SELECT rowid, metadata FROM memory_entries WHERE project_id = ?", (old,)
        ).fetchall()
        for rowid, metadata in rows:
            conn.execute(
                "UPDATE memory_entries SET project_id = ?, metadata = ? WHERE rowid = ?",
                (new, _add_tag(metadata, tag), rowid),
            )
        print(f"Folded {old} -> {new} (+tag {tag}): {len(rows)}")

    # 3. Rebuild memory_entries without the FK and component_name.
    conn.execute("""
        CREATE TABLE memory_entries_new (
            id TEXT PRIMARY KEY,
            project_id TEXT,                    -- NULL/empty for global entries
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata JSON,                      -- Flexible: tags, rationale, etc.
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        INSERT INTO memory_entries_new (rowid, id, project_id, title, content, metadata, created_at)
        SELECT rowid, id, project_id, title, content, metadata, created_at FROM memory_entries
    """)
    conn.execute("DROP TABLE memory_entries")  # drops its indexes and triggers too
    conn.execute("ALTER TABLE memory_entries_new RENAME TO memory_entries")
    conn.execute("CREATE INDEX idx_memory_project ON memory_entries(project_id)")
    conn.execute("CREATE INDEX idx_memory_created ON memory_entries(created_at DESC)")
    conn.execute("""
        CREATE TRIGGER memory_ai AFTER INSERT ON memory_entries BEGIN
            INSERT INTO memory_entries_fts(rowid, title, content)
            VALUES (new.rowid, new.title, new.content);
        END
    """)
    conn.execute("""
        CREATE TRIGGER memory_ad AFTER DELETE ON memory_entries BEGIN
            INSERT INTO memory_entries_fts(memory_entries_fts, rowid, title, content)
            VALUES ('delete', old.rowid, old.title, old.content);
        END
    """)
    conn.execute("""
        CREATE TRIGGER memory_au AFTER UPDATE ON memory_entries BEGIN
            INSERT INTO memory_entries_fts(memory_entries_fts, rowid, title, content)
            VALUES ('delete', old.rowid, old.title, old.content);
            INSERT INTO memory_entries_fts(rowid, title, content)
            VALUES (new.rowid, new.title, new.content);
        END
    """)
    # Rowids and text are unchanged, but rebuilding is cheap and guarantees
    # the external-content index matches the new table.
    conn.execute("INSERT INTO memory_entries_fts(memory_entries_fts) VALUES('rebuild')")

    # 4. Drop the dead tables.
    conn.execute("DROP TABLE IF EXISTS components")
    conn.execute("DROP TABLE IF EXISTS projects")

    # 5. Aliases.
    for dirname, project_id in ALIASES.items():
        conn.execute(
            "INSERT OR REPLACE INTO project_aliases (dirname, project_id) VALUES (?, ?)",
            (dirname, project_id),
        )
    print(f"Aliases set: {len(ALIASES)}")

    # 6. Verify before committing.
    after = dict(conn.execute("SELECT rowid, id FROM memory_entries").fetchall())
    if after != before:
        raise RuntimeError("rowid->id mapping changed; rolling back")
    conn.execute("INSERT INTO memory_entries_fts(memory_entries_fts) VALUES('integrity-check')")
    integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"integrity_check failed: {integrity}")
    leftover = conn.execute(
        "SELECT count(*) FROM memory_entries WHERE project_id IN (%s)"
        % ",".join("?" * len(PROJECT_FOLDS)),
        list(PROJECT_FOLDS),
    ).fetchone()[0]
    if leftover:
        raise RuntimeError(f"{leftover} entries still have folded project ids")
    print(f"Verified: {len(after)} entries, rowids unchanged, FTS + integrity OK")


def main():
    db_path = DB_PATH
    dry_run = False
    for arg in sys.argv[1:]:
        if arg.startswith("--db="):
            db_path = Path(arg.split("=", 1)[1]).expanduser()
        elif arg == "--dry-run":
            dry_run = True
        else:
            print(f"Unknown argument: {arg}")
            sys.exit(1)

    print(f"Database: {db_path}")
    # isolation_level=None: manage the transaction explicitly so DDL and DML
    # roll back together.
    conn = sqlite3.connect(db_path, isolation_level=None)
    try:
        migrate(conn, dry_run)
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
