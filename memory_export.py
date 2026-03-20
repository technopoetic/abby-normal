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
        "projects": rows_to_dicts(conn.execute("SELECT * FROM projects")),
        "components": rows_to_dicts(conn.execute("SELECT * FROM components")),
        "learnings": rows_to_dicts(conn.execute("SELECT * FROM learnings ORDER BY id")),
        "patterns": rows_to_dicts(conn.execute("SELECT * FROM patterns ORDER BY id")),
        "architectural_decisions": rows_to_dicts(
            conn.execute("SELECT * FROM architectural_decisions ORDER BY id")
        ),
        "pitfalls": rows_to_dicts(conn.execute("SELECT * FROM pitfalls ORDER BY id")),
        "decisions": rows_to_dicts(
            conn.execute("SELECT * FROM decisions ORDER BY project_id, id")
        ),
        "changelog": rows_to_dicts(
            conn.execute("SELECT * FROM changelog ORDER BY date DESC LIMIT 100")
        ),
        "phases": rows_to_dicts(conn.execute("SELECT * FROM phases ORDER BY project_id, id")),
        "open_questions": rows_to_dicts(
            conn.execute("SELECT * FROM open_questions ORDER BY project_id, id")
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
