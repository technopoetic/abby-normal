-- Global Memory System Database Schema
-- Version: 2.0.0 - Simplified with unified memory_entries
-- Date: 2026-03-20

-- ============================================
-- PROJECT STRUCTURE
-- ============================================

CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    full_name TEXT,
    status TEXT,
    current_phase TEXT,
    last_active DATE,
    project_type TEXT,
    git_workflow TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS components (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    name TEXT NOT NULL,
    repository TEXT NOT NULL,
    agents_file TEXT,
    tech_stack TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
    UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS project_aliases (
    dirname TEXT PRIMARY KEY,
    project_id TEXT NOT NULL
);

-- ============================================
-- UNIFIED MEMORY SYSTEM
-- All knowledge entries in one table with FTS
-- ============================================

CREATE TABLE IF NOT EXISTS memory_entries (
    id TEXT PRIMARY KEY,
    project_id TEXT,                    -- NULL for global entries
    component_name TEXT,                -- NULL for project-wide
    title TEXT NOT NULL,
    content TEXT NOT NULL,              -- Full text content
    metadata JSON,                      -- Flexible: author, rationale, outcome, tags, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Full-text search on unified memory
-- Porter stemmer: "connection" matches "connect", "connected", "connecting"
-- Prefix indexes: speeds up prefix queries (e.g. auth*)
CREATE VIRTUAL TABLE IF NOT EXISTS memory_entries_fts USING fts5(
    title,
    content,
    content=memory_entries,
    content_rowid=rowid,
    tokenize='porter unicode61',
    prefix='2 3'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory_entries BEGIN
    INSERT INTO memory_entries_fts(rowid, title, content)
    VALUES (new.rowid, new.title, new.content);
END;

CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory_entries BEGIN
    DELETE FROM memory_entries_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory_entries BEGIN
    UPDATE memory_entries_fts SET
        title = new.title,
        content = new.content
    WHERE rowid = new.rowid;
END;

-- Indexes for memory queries
CREATE INDEX IF NOT EXISTS idx_memory_project ON memory_entries(project_id);
CREATE INDEX IF NOT EXISTS idx_memory_created ON memory_entries(created_at DESC);

-- ============================================
-- VECTOR EMBEDDINGS (semantic search via sqlite-vec)
-- Requires: pysqlite3-binary, sqlite-vec, sentence-transformers
-- Created through embeddings.py / backfill_embeddings.py
-- ============================================

-- NOTE: The vec0 virtual table is created dynamically by Python code
-- because sqlite-vec must be loaded as an extension first.
-- See: ensure_vec_table() in embeddings.py
-- Table structure: CREATE VIRTUAL TABLE memory_embeddings USING vec0(embedding float[384])
-- Columns: rowid (matches memory_entries.rowid), embedding (float[384])

-- ============================================
-- VOCABULARY (controlled terms)
-- ============================================

CREATE TABLE IF NOT EXISTS vocabulary (
    category TEXT NOT NULL,
    term TEXT NOT NULL,
    added_date DATE DEFAULT (date('now')),
    PRIMARY KEY (category, term)
);