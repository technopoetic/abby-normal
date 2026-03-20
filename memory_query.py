#!/usr/bin/env python3
"""
Memory Query Helper for AI Agents - Simplified v2.0

Unified memory system with FTS search across all entry types.
"""

import sqlite3
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"


class MemoryQuery:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()

    def _rows_to_dicts(self, rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
        """Convert Row objects to dictionaries."""
        return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project details by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_project_components(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all components for a project."""
        cursor = self.conn.execute(
            """
            SELECT * FROM components 
            WHERE project_id = ?
            ORDER BY name
            """,
            (project_id,),
        )
        return self._rows_to_dicts(cursor.fetchall())

    def get_active_projects(self) -> List[Dict[str, Any]]:
        """Get all active projects."""
        cursor = self.conn.execute(
            """
            SELECT * FROM projects 
            WHERE status = 'active'
            ORDER BY last_active DESC
            """
        )
        return self._rows_to_dicts(cursor.fetchall())

    def search_memory(
        self,
        query: Optional[str] = None,
        entry_type: Optional[str] = None,
        project_id: Optional[str] = None,
        component_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search memory entries with optional filters.
        
        This searches across ALL memory types (learnings, patterns, decisions, etc.)
        
        Args:
            query: Full-text search query
            entry_type: Filter by type ('learning', 'pattern', 'decision', 'pitfall', etc.)
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
            # Escape special FTS characters (hyphens, etc.) by wrapping in quotes
            escaped_query = f'"{query}"'
            params.append(escaped_query)

        # Type filter
        if entry_type:
            where_clauses.append("m.entry_type = ?")
            params.append(entry_type)

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

    def add_memory_entry(
        self,
        entry_id: str,
        entry_type: str,
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
            entry_id: Unique ID (e.g., 'LEARN-002', 'PATTERN-003')
            entry_type: 'learning', 'pattern', 'decision', 'pitfall', 'changelog'
            title: Short title
            content: Full content/description
            project_id: Associated project (optional)
            component_name: Associated component (optional)
            metadata: Flexible JSON metadata
            tags: List of tags
        """
        self.conn.execute(
            """
            INSERT INTO memory_entries 
            (id, entry_type, project_id, component_name, title, content, metadata, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                entry_type,
                project_id,
                component_name,
                title,
                content,
                json.dumps(metadata) if metadata else None,
                json.dumps(tags) if tags else None,
            ),
        )
        self.conn.commit()

    def add_vocabulary_term(self, category: str, term: str) -> None:
        """Add a new term to controlled vocabulary."""
        self.conn.execute(
            """
            INSERT OR IGNORE INTO vocabulary (category, term) 
            VALUES (?, ?)
            """,
            (category, term),
        )
        self.conn.commit()

    def get_vocabulary(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get vocabulary terms, optionally filtered by category."""
        if category:
            cursor = self.conn.execute(
                "SELECT * FROM vocabulary WHERE category = ? ORDER BY term",
                (category,),
            )
        else:
            cursor = self.conn.execute(
                "SELECT * FROM vocabulary ORDER BY category, term"
            )
        return self._rows_to_dicts(cursor.fetchall())


def main():
    """CLI interface for quick queries."""
    if len(sys.argv) < 2:
        print("Usage: memory_query.py <command> [args...]")
        print("Commands:")
        print("  search <query> [--type=X] [--project=Y] [--tags=a,b,c] [--limit=N]")
        print("  add --type=X --title=Y --content=Z [--project=A] [--component=B] [--tags=c,d] [--metadata=JSON]")
        print("  project <project_id>")
        print("  active-projects")
        print("  vocabulary [--category=X]")
        sys.exit(1)

    command = sys.argv[1]

    with MemoryQuery() as mq:
        if command == "search":
            # Parse arguments
            query = None
            entry_type = None
            project_id = None
            tags = None
            limit = 20

            i = 2
            while i < len(sys.argv):
                arg = sys.argv[i]
                if arg.startswith("--type="):
                    entry_type = arg.split("=", 1)[1]
                elif arg.startswith("--project="):
                    project_id = arg.split("=", 1)[1]
                elif arg.startswith("--tags="):
                    tags = arg.split("=", 1)[1].split(",")
                elif arg.startswith("--limit="):
                    limit = int(arg.split("=", 1)[1])
                else:
                    query = arg
                i += 1

            results = mq.search_memory(
                query=query,
                entry_type=entry_type,
                project_id=project_id,
                tags=tags,
                limit=limit,
            )
            print(json.dumps(results, indent=2))

        elif command == "add":
            # Parse arguments
            entry_type = None
            title = None
            content = None
            project_id = None
            component_name = None
            tags = None
            metadata = None

            for arg in sys.argv[2:]:
                if arg.startswith("--type="):
                    entry_type = arg.split("=", 1)[1]
                elif arg.startswith("--title="):
                    title = arg.split("=", 1)[1]
                elif arg.startswith("--content="):
                    content = arg.split("=", 1)[1]
                elif arg.startswith("--project="):
                    project_id = arg.split("=", 1)[1]
                elif arg.startswith("--component="):
                    component_name = arg.split("=", 1)[1]
                elif arg.startswith("--tags="):
                    tags = arg.split("=", 1)[1].split(",")
                elif arg.startswith("--metadata="):
                    metadata = json.loads(arg.split("=", 1)[1])

            if not entry_type or not title or not content:
                print("Error: --type, --title, and --content are required")
                sys.exit(1)

            # Generate entry ID
            import random
            import string
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
            
            # Determine prefix based on type
            prefix = entry_type.upper()[:5]
            entry_id = f"{prefix}-{timestamp}-{suffix}"

            mq.add_memory_entry(
                entry_id=entry_id,
                entry_type=entry_type,
                title=title,
                content=content,
                project_id=project_id,
                component_name=component_name,
                metadata=metadata,
                tags=tags,
            )
            print(json.dumps({"entry_id": entry_id, "status": "added"}))

        elif command == "project":
            if len(sys.argv) < 3:
                print("Error: project_id required")
                sys.exit(1)
            project_id = sys.argv[2]
            project = mq.get_project(project_id)
            components = mq.get_project_components(project_id)
            print(json.dumps({"project": project, "components": components}, indent=2))

        elif command == "active-projects":
            projects = mq.get_active_projects()
            print(json.dumps(projects, indent=2))

        elif command == "vocabulary":
            category = None
            for arg in sys.argv[2:]:
                if arg.startswith("--category="):
                    category = arg.split("=", 1)[1]
            vocab = mq.get_vocabulary(category=category)
            print(json.dumps(vocab, indent=2))

        else:
            print(f"Unknown command: {command}")
            sys.exit(1)


if __name__ == "__main__":
    main()