#!/usr/bin/env python3
"""
Setup script for abby-normal - Global Memory System v3.0

Initializes the database, directory structure, and optional
vector embedding table for semantic search.
"""

import sqlite3
import sys
from pathlib import Path

DB_DIR = Path.home() / ".local" / "share" / "abby-normal"
DB_PATH = DB_DIR / "memory.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def setup():
    """Initialize abby-normal database."""
    print("Setting up abby-normal v3.0...")

    # Create directory
    DB_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Directory created: {DB_DIR}")

    # Initialize database with schema
    if not SCHEMA_PATH.exists():
        print(f"✗ Error: schema.sql not found at {SCHEMA_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.close()

    print(f"✓ Database initialized: {DB_PATH}")

    # Try to set up vector embeddings table
    vec_ok = False
    try:
        from embeddings import get_connection, ensure_vec_table
        vec_conn = get_connection()
        ensure_vec_table(vec_conn)
        vec_conn.close()
        vec_ok = True
    except ImportError:
        pass
    except Exception as e:
        print(f"⚠ Vector table setup failed: {e}")

    if vec_ok:
        print("✓ Vector embeddings table created (semantic search ready)")
    else:
        print("⚠ Vector embeddings not available (install sqlite-vec + sentence-transformers for semantic search)")
        print("  pip install pysqlite3-binary sqlite-vec sentence-transformers")

    print("\nNext steps:")
    print("  1. Run 'python3 backfill_embeddings.py' to embed existing entries")
    print("  2. Create symlinks: ln -s ~/code/abby-normal/memory_query.py ~/.local/bin/memory-query")
    print("  3. Start using:")
    print("     memory-query search <keyword>              # FTS keyword search")
    print("     memory-query search-semantic <description> # Semantic meaning search")
    print("     memory-query search-hybrid <query>         # Best of both")


if __name__ == "__main__":
    setup()
