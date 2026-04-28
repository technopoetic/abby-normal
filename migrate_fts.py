#!/usr/bin/env python3
"""
Migrate FTS index to porter tokenizer with prefix indexes.

Upgrades an existing abby-normal installation from the default unicode61
tokenizer to porter + prefix indexes, enabling:
  - Stemmed search: "connect" matches "connection", "connected", "connecting"
  - BM25 relevance ranking instead of date ordering
  - Faster prefix queries (auth*, test*)

Safe to run on existing databases:
  - Idempotent: detects current state and exits cleanly if already migrated
  - Non-destructive: only the FTS index is touched; memory_entries data is never modified
  - The 'rebuild' command repopulates the index from existing memory_entries rows

Usage:
    python3 ~/code/abby-normal/migrate_fts.py
    # or if symlinked:
    migrate-abby-fts
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"


def migrate(db_path: Path = DB_PATH) -> None:
    if not db_path.exists():
        print(f"✗ Database not found at {db_path}")
        print("  Run 'python3 setup.py' first to initialize the database.")
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    # Check current tokenizer via FTS5 shadow config table
    try:
        cursor = conn.execute(
            "SELECT v FROM memory_entries_fts_config WHERE k = 'tokenize'"
        )
        row = cursor.fetchone()
        current_tokenizer = row[0] if row else "unicode61"
    except sqlite3.OperationalError:
        # FTS table doesn't exist yet — nothing to migrate
        print("✓ No FTS table found — new installs use the updated schema automatically.")
        conn.close()
        return

    if "porter" in current_tokenizer:
        print(f"✓ Already using porter tokenizer ({current_tokenizer})")
        conn.close()
        return

    print(f"Current tokenizer: {current_tokenizer}")
    print("Migrating FTS index to porter tokenizer + prefix indexes...")

    # Count existing entries so we can report progress
    count = conn.execute("SELECT count(*) FROM memory_entries").fetchone()[0]

    # Drop triggers first — they reference the FTS table by name
    conn.execute("DROP TRIGGER IF EXISTS memory_ai")
    conn.execute("DROP TRIGGER IF EXISTS memory_ad")
    conn.execute("DROP TRIGGER IF EXISTS memory_au")

    # Drop the old FTS table (index only — content is safe in memory_entries)
    conn.execute("DROP TABLE IF EXISTS memory_entries_fts")

    # Recreate with porter stemmer and prefix indexes
    conn.execute("""
        CREATE VIRTUAL TABLE memory_entries_fts USING fts5(
            title,
            content,
            content=memory_entries,
            content_rowid=rowid,
            tokenize='porter unicode61',
            prefix='2 3'
        )
    """)

    # Recreate sync triggers
    conn.execute("""
        CREATE TRIGGER memory_ai AFTER INSERT ON memory_entries BEGIN
            INSERT INTO memory_entries_fts(rowid, title, content)
            VALUES (new.rowid, new.title, new.content);
        END
    """)
    conn.execute("""
        CREATE TRIGGER memory_ad AFTER DELETE ON memory_entries BEGIN
            DELETE FROM memory_entries_fts WHERE rowid = old.rowid;
        END
    """)
    conn.execute("""
        CREATE TRIGGER memory_au AFTER UPDATE ON memory_entries BEGIN
            UPDATE memory_entries_fts SET
                title = new.title,
                content = new.content
            WHERE rowid = new.rowid;
        END
    """)

    # Rebuild the FTS index from existing memory_entries data
    print(f"Rebuilding FTS index for {count} existing entries...")
    conn.execute("INSERT INTO memory_entries_fts(memory_entries_fts) VALUES('rebuild')")

    conn.commit()
    conn.close()
    print("✓ Migration complete — porter stemming and BM25 ranking now active.")


if __name__ == "__main__":
    migrate()
