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
CREATE VIRTUAL TABLE IF NOT EXISTS memory_entries_fts USING fts5(
    title,
    content,
    content=memory_entries,
    content_rowid=rowid
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
-- ORCHESTRATION SYSTEM
-- Multi-agent coordination (separate from memory)
-- ============================================

CREATE TABLE IF NOT EXISTS orchestration_sessions (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    component_name TEXT,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    max_parallel_agents INTEGER DEFAULT 3,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS waves (
    id TEXT PRIMARY KEY,
    orchestration_id TEXT NOT NULL,
    wave_number INTEGER NOT NULL,
    status TEXT DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    synthesis_summary TEXT,
    FOREIGN KEY (orchestration_id) REFERENCES orchestration_sessions(id) ON DELETE CASCADE,
    UNIQUE(orchestration_id, wave_number)
);

CREATE TABLE IF NOT EXISTS agent_sessions (
    id TEXT PRIMARY KEY,
    orchestration_id TEXT NOT NULL,
    wave_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    agent_type TEXT NOT NULL,
    task_description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    artifacts_json TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    FOREIGN KEY (orchestration_id) REFERENCES orchestration_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (wave_id) REFERENCES waves(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    task_id TEXT NOT NULL,
    depends_on_task_id TEXT NOT NULL,
    PRIMARY KEY (task_id, depends_on_task_id),
    FOREIGN KEY (task_id) REFERENCES agent_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_task_id) REFERENCES agent_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS interface_contracts (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    contract_type TEXT NOT NULL,
    contract_name TEXT NOT NULL,
    language TEXT NOT NULL,
    definition_json TEXT NOT NULL,
    source_file TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES orchestration_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (agent_id) REFERENCES agent_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS contract_mismatches (
    id TEXT PRIMARY KEY,
    orchestration_id TEXT NOT NULL,
    wave_id TEXT NOT NULL,
    contract_a_id TEXT NOT NULL,
    contract_b_id TEXT NOT NULL,
    mismatch_type TEXT NOT NULL,
    details TEXT NOT NULL,
    fix_agent_id TEXT,
    fix_attempts INTEGER DEFAULT 0,
    status TEXT DEFAULT 'detected',
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (orchestration_id) REFERENCES orchestration_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (wave_id) REFERENCES waves(id) ON DELETE CASCADE,
    FOREIGN KEY (contract_a_id) REFERENCES interface_contracts(id) ON DELETE CASCADE,
    FOREIGN KEY (contract_b_id) REFERENCES interface_contracts(id) ON DELETE CASCADE,
    FOREIGN KEY (fix_agent_id) REFERENCES agent_sessions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS synthesis_results (
    id TEXT PRIMARY KEY,
    wave_id TEXT NOT NULL,
    orchestration_id TEXT NOT NULL,
    synthesis_type TEXT NOT NULL,
    content TEXT NOT NULL,
    applied_to_agents TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (wave_id) REFERENCES waves(id) ON DELETE CASCADE,
    FOREIGN KEY (orchestration_id) REFERENCES orchestration_sessions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS project_languages (
    project_id TEXT PRIMARY KEY,
    detected_language TEXT NOT NULL,
    detection_confidence REAL,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

-- Orchestration indexes
CREATE INDEX IF NOT EXISTS idx_orchestration_project ON orchestration_sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_waves_orchestration ON waves(orchestration_id);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_wave ON agent_sessions(wave_id);
CREATE INDEX IF NOT EXISTS idx_contracts_session ON interface_contracts(session_id);
CREATE INDEX IF NOT EXISTS idx_contracts_language ON interface_contracts(language);
CREATE INDEX IF NOT EXISTS idx_mismatches_wave ON contract_mismatches(wave_id);
CREATE INDEX IF NOT EXISTS idx_mismatches_status ON contract_mismatches(status);

-- ============================================
-- VOCABULARY (controlled terms)
-- ============================================

CREATE TABLE IF NOT EXISTS vocabulary (
    category TEXT NOT NULL,
    term TEXT NOT NULL,
    added_date DATE DEFAULT (date('now')),
    PRIMARY KEY (category, term)
);