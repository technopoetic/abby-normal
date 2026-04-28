#!/usr/bin/env python3
"""
Memory Query Helper for AI Agents - v2.1

Unified memory system with FTS5 search across all entry types.

Search uses porter stemming and BM25 relevance ranking:
  - "connect" matches "connection", "connected", "connecting"
  - Results ordered by relevance when a query is given, by date otherwise
  - Search results include an "excerpt" field showing match context

FTS5 query syntax is supported when detected in the query string:
  - term1 term2        implicit AND (both required)
  - term1 OR term2     either term
  - term1 NOT term2    first without second
  - "exact phrase"     adjacent phrase
  - term*              prefix match (use short prefixes: auth* not authenticat*)
  - NEAR(t1 t2, N)     within N tokens of each other
  - col: term          search specific column (title or content)
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

    def _build_fts_query(self, query: str) -> str:
        """
        Build an FTS5 query from user input.

        If the query already contains FTS5 syntax operators, pass it through
        unchanged — the caller knows what they're doing.

        Otherwise, split on whitespace and quote any tokens that contain FTS5
        special characters. Multiple tokens become an implicit AND.

        Note on porter stemming + prefixes: use short prefixes (auth*, test*).
        Mid-word prefixes like authenticat* won't match because the stemmer
        reduces "authentication" to a stem that doesn't share that prefix.
        """
        stripped = query.strip()
        upper = stripped.upper()

        # Detect explicit FTS5 syntax — pass through unchanged
        fts_operators = (" AND ", " OR ", " NOT ")
        if (any(op in f" {upper} " for op in fts_operators) or
                "NEAR(" in upper or
                '"' in stripped or
                stripped.endswith("*")):
            return stripped

        # Per-token escaping: wrap tokens containing special chars in quotes
        special = set("():-^!")
        tokens = stripped.split()
        escaped = []
        for token in tokens:
            if any(c in token for c in special):
                escaped.append(f'"{token}"')
            else:
                escaped.append(token)
        return " ".join(escaped)  # implicit AND

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
        project_id: Optional[str] = None,
        component_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        Search memory entries with optional filters.

        When a query is given, results are ranked by BM25 relevance and each
        result includes an "excerpt" field with match context (matches wrapped
        in square brackets).

        When no query is given (filter-only), results are ordered by
        created_at descending. No excerpt is included.

        Args:
            query: Full-text search query. Supports FTS5 syntax when detected.
            project_id: Filter by project
            component_name: Filter by component
            tags: Filter by tags (entry must have ALL specified tags)
            limit: Max results to return (default 20)
        """
        if query:
            return self._search_with_fts(query, project_id, component_name, tags, limit)
        else:
            return self._search_without_fts(project_id, component_name, tags, limit)

    def _search_with_fts(
        self,
        query: str,
        project_id: Optional[str],
        component_name: Optional[str],
        tags: Optional[List[str]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        FTS-driven search: BM25 relevance ranking + excerpt.

        The FTS table is the primary driver so bm25() and snippet() work.
        memory_entries is joined to retrieve project_id, metadata, etc.

        snippet() uses column -1 (auto-select best column for match context).
        Matched terms are wrapped in square brackets in the excerpt.
        """
        fts_query = self._build_fts_query(query)

        sql = """
            SELECT m.id, m.project_id, m.component_name, m.title, m.content,
                   m.metadata, m.created_at,
                   bm25(memory_entries_fts) AS bm25_score,
                   snippet(memory_entries_fts, -1, '[', ']', '...', 20) AS excerpt
            FROM memory_entries_fts
            JOIN memory_entries m ON m.rowid = memory_entries_fts.rowid
            WHERE memory_entries_fts MATCH ?
        """
        params: List[Any] = [fts_query]

        if project_id:
            sql += " AND m.project_id = ?"
            params.append(project_id)

        if component_name:
            sql += " AND m.component_name = ?"
            params.append(component_name)

        if tags:
            for tag in tags:
                sql += " AND json_extract(m.metadata, '$.tags') LIKE ?"
                params.append(f'%"{tag}"%')

        sql += " ORDER BY memory_entries_fts.rank LIMIT ?"
        params.append(limit)

        cursor = self.conn.execute(sql, params)
        return self._rows_to_dicts(cursor.fetchall())

    def _search_without_fts(
        self,
        project_id: Optional[str],
        component_name: Optional[str],
        tags: Optional[List[str]],
        limit: int,
    ) -> List[Dict[str, Any]]:
        """
        Filter-only search (no query): ordered by created_at descending.
        No BM25 ranking or excerpt — can't compute those without a MATCH.
        """
        sql = "SELECT * FROM memory_entries m"
        where_clauses = []
        params: List[Any] = []

        if project_id:
            where_clauses.append("m.project_id = ?")
            params.append(project_id)

        if component_name:
            where_clauses.append("m.component_name = ?")
            params.append(component_name)

        if tags:
            for tag in tags:
                where_clauses.append("json_extract(m.metadata, '$.tags') LIKE ?")
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
        title: str,
        content: str,
        project_id: Optional[str] = None,
        component_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ):
        """
        Add a new memory entry.

        Args:
            entry_id: Unique ID (auto-generated by CLI as MEM-YYYYMMDD-HHMMSS-xxxxxx)
            title: Short title
            content: Full content/description
            project_id: Associated project (optional)
            component_name: Associated component (optional)
            metadata: Flexible JSON metadata
            tags: List of tags (merged into metadata)
        """
        final_metadata = metadata.copy() if metadata else {}
        if tags:
            final_metadata["tags"] = tags

        self.conn.execute(
            """
            INSERT INTO memory_entries
            (id, project_id, component_name, title, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                entry_id,
                project_id,
                component_name,
                title,
                content,
                json.dumps(final_metadata) if final_metadata else None,
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
        print("  search <query> [--project=Y] [--tags=a,b,c] [--limit=N]")
        print("  add --title=Y --content=Z [--project=A] [--component=B] [--tags=c,d] [--metadata=JSON]")
        print("  project <project_id>")
        print("  active-projects")
        print("  vocabulary [--category=X]")
        print()
        print("Search uses porter stemming + BM25 ranking.")
        print("FTS5 syntax supported: AND, OR, NOT, NEAR(t1 t2,N), term*, \"phrase\"")
        print("Results include 'excerpt' (match context) and 'bm25_score' when a query is given.")
        sys.exit(1)

    command = sys.argv[1]

    with MemoryQuery() as mq:
        if command == "search":
            query = None
            project_id = None
            tags = None
            limit = 20

            i = 2
            while i < len(sys.argv):
                arg = sys.argv[i]
                if arg.startswith("--project="):
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
                project_id=project_id,
                tags=tags,
                limit=limit,
            )
            print(json.dumps(results, indent=2))

        elif command == "add":
            title = None
            content = None
            project_id = None
            component_name = None
            tags = None
            metadata = None

            for arg in sys.argv[2:]:
                if arg.startswith("--title="):
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

            if not title or not content:
                print("Error: --title and --content are required")
                sys.exit(1)

            import random
            import string
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
            entry_id = f"MEM-{timestamp}-{suffix}"

            mq.add_memory_entry(
                entry_id=entry_id,
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
