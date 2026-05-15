#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Query Helper for AI Agents - v3.0 with Semantic Search

To use semantic search features, activate the venv first:
  source ~/code/abby-normal/.venv/bin/activate
Or run directly:
  ~/code/abby-normal/.venv/bin/python memory_query.py <command>

Unified memory system with FTS5 search, semantic vector search,
and hybrid (FTS + semantic) search across all entry types.

v2.1 (remote): Porter stemming, BM25 ranking, FTS5 query syntax, snippets
v3.0 (local):  Semantic search via sqlite-vec, hybrid search, auto-embedding

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

import json
import os
import sqlite3
import struct
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Auto-activate venv if not already in it
_ABBY_VENV = os.path.expanduser("~/code/abby-normal/.venv")
if not os.environ.get("ABBY_NORMAL_IN_VENV") and os.path.isdir(_ABBY_VENV):
    import subprocess
    result = subprocess.run(
        [os.path.join(_ABBY_VENV, "bin", "python3")] + sys.argv,
        env={**os.environ, "ABBY_NORMAL_IN_VENV": "1"},
    )
    sys.exit(result.returncode)

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"

# Sentinel: if we can't load sqlite-vec, fall back gracefully
_VEC_AVAILABLE = False


def _try_import_vec():
    """Check if sqlite-vec + pysqlite3 are available."""
    try:
        import pysqlite3  # noqa: F401
        import sqlite_vec  # noqa: F401
        return True
    except ImportError:
        return False


_VEC_AVAILABLE = _try_import_vec()


class MemoryQuery:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS project_aliases "
            "(dirname TEXT PRIMARY KEY, project_id TEXT NOT NULL)"
        )
        # Will be lazily created if needed for vector ops
        self._vec_conn = None
        # Embedding model (lazy)
        self._model = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._vec_conn:
            self._vec_conn.close()
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

    def _get_vec_connection(self):
        """Get a connection with sqlite-vec loaded (lazy, shared)."""
        if self._vec_conn is None:
            if not _VEC_AVAILABLE:
                raise RuntimeError(
                    "Vector search requires pysqlite3-binary and sqlite-vec. "
                    "Install with: pip install pysqlite3-binary sqlite-vec sentence-transformers"
                )
            from embeddings import get_connection, ensure_vec_table
            self._vec_conn = get_connection(self.db_path)
            ensure_vec_table(self._vec_conn)
        return self._vec_conn

    def _get_model(self):
        """Lazily load the sentence-transformers model."""
        if self._model is None:
            from embeddings import get_model
            self._model = get_model()
        return self._model

    def _encode_text(self, text: str) -> bytes:
        """Encode text to packed float32 vector."""
        from embeddings import encode_text
        return encode_text(text)

    # ============================================
    # PROJECT QUERIES
    # ============================================

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

    # ============================================
    # PROJECT ALIASES
    # ============================================

    def resolve_project(self, dirname: str) -> str:
        row = self.conn.execute(
            "SELECT project_id FROM project_aliases WHERE dirname = ?", (dirname,)
        ).fetchone()
        return row[0] if row else dirname

    def add_alias(self, dirname: str, project_id: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO project_aliases (dirname, project_id) VALUES (?, ?)",
            (dirname, project_id),
        )
        self.conn.commit()

    def remove_alias(self, dirname: str) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM project_aliases WHERE dirname = ?", (dirname,)
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def list_aliases(self) -> List[Dict[str, str]]:
        cursor = self.conn.execute(
            "SELECT dirname, project_id FROM project_aliases ORDER BY project_id, dirname"
        )
        return [{"dirname": r[0], "project_id": r[1]} for r in cursor.fetchall()]

    # ============================================
    # FTS SEARCH (v2.1: porter stemmer, BM25, snippets)
    # ============================================

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
        results = self._rows_to_dicts(cursor.fetchall())

        # Apply recency boost and re-rank
        now = datetime.now()
        for entry in results:
            score = entry.get("bm25_score", 0.0) or 0.0
            try:
                age_days = (now - datetime.fromisoformat(entry["created_at"])).days
                if age_days <= 7:
                    score -= 0.2  # bm25 scores are negative (lower = better)
                elif age_days <= 30:
                    score -= 0.1
            except (ValueError, TypeError, KeyError):
                pass
            entry["bm25_score"] = score
        results.sort(key=lambda e: e.get("bm25_score", 0.0) or 0.0)

        return results

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

    # ============================================
    # SEMANTIC SEARCH (v3.0: vector similarity)
    # ============================================

    def search_semantic(
        self,
        query: str,
        project_id: Optional[str] = None,
        component_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        distance_threshold: float = 1.2,
    ) -> List[Dict[str, Any]]:
        """
        Search memory entries by semantic similarity using vector embeddings.

        Finds entries that *mean* something similar to the query, even if they
        don't share the same keywords. For example, "payment problems" will find
        entries about "credit card failures" or "Stripe webhook errors".

        Args:
            query: Natural language query
            project_id: Filter by project
            component_name: Filter by component
            tags: Filter by tags (must have ALL specified tags)
            limit: Max results to return
            distance_threshold: Max cosine distance (0=identical, ~1.0=typical match, >1.5=unrelated)
        """
        vec_conn = self._get_vec_connection()
        query_embedding = self._encode_text(query)

        # Get vector search results with distances
        vec_results = vec_conn.execute(
            "SELECT rowid, distance FROM memory_embeddings "
            "WHERE embedding MATCH ? AND distance <= ? "
            "ORDER BY distance LIMIT ?",
            (query_embedding, distance_threshold, limit * 3),  # Over-fetch for filtering
        ).fetchall()

        if not vec_results:
            return []

        # Build filter conditions
        rowids = [r[0] for r in vec_results]
        distances = {r[0]: r[1] for r in vec_results}

        # Fetch actual entries from main connection
        placeholders = ",".join("?" * len(rowids))
        sql = f"SELECT m.*, m.rowid as _rowid FROM memory_entries m WHERE m.rowid IN ({placeholders})"
        params = list(rowids)

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

        cursor = self.conn.execute(sql, params)
        entries = self._rows_to_dicts(cursor.fetchall())

        # Attach distance info and sort by semantic similarity
        for entry in entries:
            entry["semantic_distance"] = distances.get(entry.get("_rowid"), None)
            entry.pop("_rowid", None)

        entries.sort(key=lambda e: e.get("semantic_distance", 999) or 999)

        return entries[:limit]

    # ============================================
    # HYBRID SEARCH (v3.0: FTS + semantic combined)
    # ============================================

    def search_hybrid(
        self,
        query: str,
        project_id: Optional[str] = None,
        component_name: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        semantic_weight: float = 0.7,
        fts_weight: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining FTS5 keyword matching + semantic vector similarity.

        This is the best of both worlds:
        - FTS5 finds exact keyword matches (proper nouns, specific terms)
        - Semantic finds conceptually related entries (different words, same meaning)
        - Combined ranking surfaces the most relevant results from both

        Args:
            query: Search query
            project_id: Filter by project
            component_name: Filter by component
            tags: Filter by tags
            limit: Max results
            semantic_weight: Weight for semantic scores (0-1, default 0.7)
            fts_weight: Weight for FTS scores (0-1, default 0.3)
        """
        # Run both searches
        fts_results = self.search_memory(
            query=query,
            project_id=project_id,
            component_name=component_name,
            tags=tags,
            limit=limit * 2,
        )

        semantic_results = self.search_semantic(
            query=query,
            project_id=project_id,
            component_name=component_name,
            tags=tags,
            limit=limit * 2,
            distance_threshold=1.5,
        )

        # Build candidate union with scores
        candidates: Dict[str, Dict[str, Any]] = {}

        # Score FTS results (rank based on position — earlier = better)
        for i, entry in enumerate(fts_results):
            eid = entry["id"]
            # Normalized rank score: 1.0 (first result) to ~0.0 (last)
            fts_score = 1.0 - (i / max(len(fts_results), 1))
            candidates[eid] = {
                **entry,
                "fts_rank": i + 1,
                "fts_score": fts_score,
                "semantic_distance": None,
                "semantic_score": 0.0,
            }

        # Score semantic results (convert distance to score: 0 distance = 1.0 score)
        for entry in semantic_results:
            eid = entry["id"]
            dist = entry.get("semantic_distance", 1.5) or 1.5
            # Convert distance to score: 0 dist -> 1.0, 1.5 dist -> 0.0
            semantic_score = max(0.0, 1.0 - dist / 1.5)

            if eid in candidates:
                # Entry found by both FTS and semantic — boost it
                candidates[eid]["semantic_distance"] = dist
                candidates[eid]["semantic_score"] = semantic_score
            else:
                candidates[eid] = {
                    **entry,
                    "fts_rank": None,
                    "fts_score": 0.0,
                    "semantic_distance": dist,
                    "semantic_score": semantic_score,
                }

        # Compute combined score
        now = datetime.now()
        for eid, c in candidates.items():
            c["combined_score"] = (
                semantic_weight * c["semantic_score"] + fts_weight * c["fts_score"]
            )
            # Bonus for appearing in both result sets
            if c["fts_score"] > 0 and c["semantic_score"] > 0:
                c["combined_score"] += 0.15
            # Recency boost
            try:
                age_days = (now - datetime.fromisoformat(c["created_at"])).days
                if age_days <= 7:
                    c["combined_score"] += 0.2
                elif age_days <= 30:
                    c["combined_score"] += 0.1
            except (ValueError, TypeError, KeyError):
                pass

        # Sort by combined score
        ranked = sorted(candidates.values(), key=lambda e: e["combined_score"], reverse=True)

        # Clean up internal scoring fields from output
        for entry in ranked:
            entry.pop("fts_score", None)
            entry.pop("semantic_score", None)
            entry.pop("combined_score", None)

        return ranked[:limit]

    # ============================================
    # ADD / DELETE MEMORY ENTRIES (with auto-embedding)
    # ============================================

    def add_memory_entry(
        self,
        entry_id: str,
        title: str,
        content: str,
        project_id: Optional[str] = None,
        component_name: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
        generate_embedding: bool = True,
    ):
        """
        Add a new memory entry.

        If generate_embedding=True and sqlite-vec is available, automatically
        generates and stores a vector embedding for semantic search.

        Args:
            entry_id: Unique ID (auto-generated by CLI as MEM-YYYYMMDD-HHMMSS-xxxxxx)
            title: Short title
            content: Full content/description
            project_id: Associated project (optional)
            component_name: Associated component (optional)
            metadata: Flexible JSON metadata
            tags: List of tags (merged into metadata)
            generate_embedding: Whether to auto-generate vector embedding
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

        # Generate and store embedding if possible
        if generate_embedding and _VEC_AVAILABLE:
            try:
                rowid = self.conn.execute(
                    "SELECT rowid FROM memory_entries WHERE id = ?", (entry_id,)
                ).fetchone()[0]

                embedding = self._encode_text(f"{title} {content}")

                vec_conn = self._get_vec_connection()
                # Handle rowid reuse: if a deleted entry's orphaned embedding
                # still exists, remove it before inserting the new one
                vec_conn.execute(
                    "DELETE FROM memory_embeddings WHERE rowid = ?", (rowid,)
                )
                vec_conn.execute(
                    "INSERT INTO memory_embeddings(rowid, embedding) VALUES (?, ?)",
                    (rowid, embedding),
                )
                vec_conn.commit()
            except Exception as e:
                # Don't fail the insert if embedding fails — it's an enhancement, not a requirement
                print(f"Warning: embedding generation failed: {e}", file=sys.stderr)

    def delete_memory_entry(self, entry_id: str):
        """
        Delete a memory entry and its associated embedding.

        Args:
            entry_id: The ID of the entry to delete
        Returns:
            True if the entry was found and deleted, False if not found
        """
        row = self.conn.execute(
            "SELECT rowid FROM memory_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if not row:
            return False

        rowid = row[0]

        # Delete from main table
        self.conn.execute("DELETE FROM memory_entries WHERE id = ?", (entry_id,))
        self.conn.commit()

        # Delete embedding if vec is available
        if _VEC_AVAILABLE:
            try:
                vec_conn = self._get_vec_connection()
                vec_conn.execute(
                    "DELETE FROM memory_embeddings WHERE rowid = ?", (rowid,)
                )
                vec_conn.commit()
            except Exception:
                pass  # Best-effort cleanup

        return True

    # ============================================
    # VOCABULARY
    # ============================================

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


# ============================================
# CLI
# ============================================


def main():
    """CLI interface for memory queries."""
    if len(sys.argv) < 2:
        _print_help()
        sys.exit(1)

    command = sys.argv[1]

    with MemoryQuery() as mq:
        if command == "search":
            _cmd_unified_search(mq)
        elif command in ("search-semantic", "search-hybrid"):
            _cmd_unified_search(mq)
        elif command == "add":
            _cmd_add(mq)
        elif command == "delete":
            _cmd_delete(mq)
        elif command == "project":
            _cmd_project(mq)
        elif command == "active-projects":
            _cmd_active_projects(mq)
        elif command == "vocabulary":
            _cmd_vocabulary(mq)
        elif command == "alias":
            _cmd_alias(mq)
        elif command == "resolve-project":
            _cmd_resolve_project(mq)
        else:
            print(f"Unknown command: {command}")
            _print_help()
            sys.exit(1)


def _print_help():
    print("Usage: memory_query.py <command> [args...]")
    print()
    print("Search:")
    print("  search <query> [--project=Y] [--tags=a,b,c] [--limit=N]")
    print("    Hybrid FTS + semantic search (falls back to FTS-only if sqlite-vec unavailable)")
    print()
    print("Memory:")
    print("  add --title=Y --content=Z [--project=A] [--component=B] [--tags=c,d] [--no-embed]")
    print("  delete <entry_id>")
    print()
    print("Projects:")
    print("  alias list                              List all directory-to-project aliases")
    print("  alias add <dirname> <project-id>        Map a directory to a project")
    print("  alias remove <dirname>                  Remove an alias")
    print("  resolve-project <dirname>               Resolve dirname to project ID")
    print("  project <project_id>                    Show project details")
    print("  active-projects                         List active projects")
    print()
    print("Other:")
    print("  vocabulary [--category=X]")
    print()
    print("FTS5 syntax supported: AND, OR, NOT, NEAR(t1 t2,N), term*, \"phrase\"")


def _parse_common_args() -> Dict[str, Any]:
    """Parse common arguments from sys.argv."""
    project_id = None
    tags = None
    limit = None
    query_parts = []

    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg.startswith("--project="):
            project_id = arg.split("=", 1)[1]
        elif arg.startswith("--tags="):
            tags = arg.split("=", 1)[1].split(",")
        elif arg.startswith("--limit="):
            limit = int(arg.split("=", 1)[1])
        elif arg.startswith("--threshold="):
            pass  # Handled per-command
        elif not arg.startswith("--"):
            query_parts.append(arg)
        i += 1

    query = " ".join(query_parts) if query_parts else None
    return {"query": query, "project_id": project_id, "tags": tags, "limit": limit}


def _cmd_unified_search(mq: MemoryQuery):
    args = _parse_common_args()
    limit = args["limit"] or 10

    if args["query"] and _VEC_AVAILABLE:
        results = mq.search_hybrid(
            query=args["query"],
            project_id=args["project_id"],
            tags=args["tags"],
            limit=limit,
        )
    else:
        results = mq.search_memory(
            query=args["query"],
            project_id=args["project_id"],
            tags=args["tags"],
            limit=limit,
        )

    print(json.dumps(results, indent=2, default=str))


def _cmd_add(mq: MemoryQuery):
    title = None
    content = None
    project_id = None
    component_name = None
    tags = None
    metadata = None
    no_embed = False

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
        elif arg == "--no-embed":
            no_embed = True

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
        generate_embedding=not no_embed,
    )

    embed_status = "with embedding" if (not no_embed and _VEC_AVAILABLE) else "without embedding"
    print(json.dumps({"entry_id": entry_id, "status": "added", "embedding": embed_status}))


def _cmd_delete(mq: MemoryQuery):
    if len(sys.argv) < 3:
        print("Error: entry_id required")
        sys.exit(1)
    entry_id = sys.argv[2]
    deleted = mq.delete_memory_entry(entry_id)
    print(json.dumps({"entry_id": entry_id, "deleted": deleted}))


def _cmd_project(mq: MemoryQuery):
    if len(sys.argv) < 3:
        print("Error: project_id required")
        sys.exit(1)
    project_id = sys.argv[2]
    project = mq.get_project(project_id)
    components = mq.get_project_components(project_id)
    print(json.dumps({"project": project, "components": components}, indent=2))


def _cmd_active_projects(mq: MemoryQuery):
    projects = mq.get_active_projects()
    print(json.dumps(projects, indent=2))


def _cmd_alias(mq: MemoryQuery):
    subcmd = sys.argv[2] if len(sys.argv) > 2 else "list"

    if subcmd == "list":
        print(json.dumps(mq.list_aliases(), indent=2))
    elif subcmd == "add":
        if len(sys.argv) < 5:
            print("Usage: alias add <dirname> <project-id>")
            sys.exit(1)
        dirname, project_id = sys.argv[3], sys.argv[4]
        mq.add_alias(dirname, project_id)
        print(json.dumps({"dirname": dirname, "project_id": project_id, "status": "added"}))
    elif subcmd == "remove":
        if len(sys.argv) < 4:
            print("Usage: alias remove <dirname>")
            sys.exit(1)
        removed = mq.remove_alias(sys.argv[3])
        print(json.dumps({"dirname": sys.argv[3], "removed": removed}))
    else:
        print(f"Unknown alias subcommand: {subcmd}")
        print("Usage: alias [list | add <dirname> <project-id> | remove <dirname>]")
        sys.exit(1)


def _cmd_resolve_project(mq: MemoryQuery):
    if len(sys.argv) < 3:
        print("Error: dirname required")
        sys.exit(1)
    print(mq.resolve_project(sys.argv[2]))


def _cmd_vocabulary(mq: MemoryQuery):
    category = None
    for arg in sys.argv[2:]:
        if arg.startswith("--category="):
            category = arg.split("=", 1)[1]
    vocab = mq.get_vocabulary(category=category)
    print(json.dumps(vocab, indent=2))


if __name__ == "__main__":
    main()
