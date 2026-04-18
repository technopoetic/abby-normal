#!/usr/bin/env python3
"""
Migrate existing entries from typed (entry_type column) to untyped schema.

This script:
1. Reads all existing entries from memory_entries
2. For each entry, merges entry_type and existing tags into metadata
3. Alters the table to drop entry_type and tags columns
4. Verifies the migration

SQLite 3.35.0+ supports DROP COLUMN.
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"

def migrate():
    conn = sqlite3.connect(DB_PATH)
    
    # Step 1: Check current schema
    cursor = conn.execute("PRAGMA table_info(memory_entries)")
    columns = {row[1] for row in cursor.fetchall()}
    
    if 'entry_type' not in columns:
        print("✓ Database already uses untyped schema")
        conn.close()
        return
    
    print(f"Found columns: {columns}")
    
    # Step 2: Read existing entries
    cursor = conn.execute("SELECT id, entry_type, metadata, tags FROM memory_entries")
    rows = cursor.fetchall()
    print(f"Found {len(rows)} entries to migrate")
    
    # Step 3: Migrate each entry
    for row in rows:
        entry_id, entry_type, metadata, tags = row
        
        # Parse existing JSON fields
        meta = json.loads(metadata) if metadata else {}
        tag_list = json.loads(tags) if tags else []
        
        # Add entry_type as a tag if it exists and isn't already in tag_list
        if entry_type and entry_type not in tag_list:
            tag_list.append(entry_type)
        
        # Add tags to metadata
        meta['tags'] = tag_list
        
        # Update entry with merged metadata
        conn.execute("""
            UPDATE memory_entries 
            SET metadata = ?
            WHERE id = ?
        """, (json.dumps(meta), entry_id))
        
        print(f"  Migrated: {entry_id} (entry_type={entry_type}, tags={tag_list})")
    
    conn.commit()
    print("✓ Migrated entry_type and tags into metadata")
    
    # Step 4: Alter table to drop old columns
    # SQLite 3.35.0+ supports DROP COLUMN
    print("Dropping old columns...")
    
    # Drop tags column first (if not nullable might cause issues), then entry_type
    try:
        conn.execute("ALTER TABLE memory_entries DROP COLUMN tags")
        print("  Dropped tags column")
    except Exception as e:
        print(f"  Could not drop tags column: {e}")
    
    try:
        conn.execute("ALTER TABLE memory_entries DROP COLUMN entry_type")
        print("  Dropped entry_type column")
    except Exception as e:
        print(f"  Could not drop entry_type column: {e}")
    
    conn.commit()
    
    # Step 5: Drop the index on entry_type
    try:
        conn.execute("DROP INDEX idx_memory_type")
        print("  Dropped idx_memory_type index")
    except Exception as e:
        print(f"  Could not drop idx_memory_type index: {e}")
    
    conn.commit()
    
    # Step 6: Verify
    cursor = conn.execute("PRAGMA table_info(memory_entries)")
    final_columns = {row[1] for row in cursor.fetchall()}
    print(f"\nFinal columns: {final_columns}")
    
    # Check indexes
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='memory_entries'")
    indexes = [row[0] for row in cursor.fetchall()]
    print(f"Indexes: {indexes}")
    
    # Verify data is accessible
    cursor = conn.execute("SELECT COUNT(*) FROM memory_entries")
    count = cursor.fetchone()[0]
    print(f"Entries remaining: {count}")
    
    conn.close()
    print("\n✓ Migration complete!")

if __name__ == "__main__":
    migrate()