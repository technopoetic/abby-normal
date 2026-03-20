#!/usr/bin/env python3
"""
Setup script for abby-normal - Global Memory System

Initializes the database and directory structure.
"""

import sqlite3
import sys
from pathlib import Path

DB_DIR = Path.home() / ".local" / "share" / "abby-normal"
DB_PATH = DB_DIR / "memory.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def setup():
    """Initialize abby-normal database."""
    print("Setting up abby-normal...")
    
    # Create directory
    DB_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Directory created: {DB_DIR}")
    
    # Check if database already exists
    if DB_PATH.exists():
        print(f"✓ Database already exists at: {DB_PATH}")
        print("  Run 'python3 seed_database.py' to add initial data if needed.")
        return
    
    # Initialize database with schema
    if not SCHEMA_PATH.exists():
        print(f"✗ Error: schema.sql not found at {SCHEMA_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())
    conn.close()
    
    print(f"✓ Database initialized: {DB_PATH}")
    print("\nNext steps:")
    print("  1. Run 'python3 seed_database.py' to add initial data")
    print("  2. Create symlinks: ln -s ~/code/abby-normal/memory_query.py ~/.local/bin/memory-query")
    print("  3. Start using: memory-query search <keyword>")


if __name__ == "__main__":
    setup()