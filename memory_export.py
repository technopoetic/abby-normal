#!/usr/bin/env python3
"""
Memory Export Tool

Exports memory.db to human-readable JSON format for review.
"""

import sqlite3
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"


def export_memory(db_path: Path = DB_PATH, output_path: Optional[Path] = None) -> Dict[str, Any]:
    """Export entire memory database to JSON."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    def rows_to_dicts(cursor):
        return [dict(row) for row in cursor.fetchall()]

    export = {
        "meta": {
            "exported_at": None,  # Will be filled by SQL
            "database_version": "1.0.0",
        },
        "memory_entries": rows_to_dicts(
            conn.execute("SELECT * FROM memory_entries ORDER BY created_at")
        ),
        "project_aliases": rows_to_dicts(
            conn.execute("SELECT * FROM project_aliases ORDER BY project_id, dirname")
        ),
        "vocabulary": rows_to_dicts(
            conn.execute("SELECT * FROM vocabulary ORDER BY category, term")
        ),
    }

    # Get current timestamp from database
    export["meta"]["exported_at"] = conn.execute("SELECT datetime('now')").fetchone()[0]

    conn.close()

    if output_path:
        with open(output_path, "w") as f:
            json.dump(export, f, indent=2, default=str)
        print(f"Exported to {output_path}")
    else:
        print(json.dumps(export, indent=2, default=str))

    return export


if __name__ == "__main__":
    output_file = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    export_memory(output_path=output_file)
