#!/usr/bin/env python3
"""
Orchestration Helper for Multi-Agent Coordination

Provides functions for wave-based orchestration, contract management,
and agent session tracking.
"""

import sqlite3
import json
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"


@dataclass
class AgentSession:
    """Represents an agent session."""
    id: str
    orchestration_id: str
    wave_id: str
    agent_name: str
    agent_type: str
    task_description: str
    status: str
    artifacts_json: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class InterfaceContract:
    """Represents an extracted interface contract."""
    id: str
    session_id: str
    agent_id: str
    contract_type: str
    contract_name: str
    language: str
    definition_json: str
    source_file: Optional[str] = None
    extracted_at: Optional[str] = None


class OrchestrationManager:
    """Manages multi-agent orchestration state."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
    
    def _generate_id(self, prefix: str) -> str:
        """Generate a unique ID with prefix."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        import random
        suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
        return f"{prefix}-{timestamp}-{suffix}"
    
    def _rows_to_dicts(self, rows: List[sqlite3.Row]) -> List[Dict[str, Any]]:
        """Convert Row objects to dictionaries."""
        return [dict(row) for row in rows]
    
    def detect_project_language(self, project_path: str) -> Tuple[str, float]:
        """
        Detect primary language of a project.
        
        Returns:
            Tuple of (language, confidence)
        """
        path = Path(project_path)
        if not path.exists():
            return ("unknown", 0.0)
        
        extensions = {}
        total_files = 0
        
        for file in path.rglob("*"):
            if file.is_file():
                total_files += 1
                ext = file.suffix.lower()
                if ext in ['.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs', '.java']:
                    extensions[ext] = extensions.get(ext, 0) + 1
        
        if not extensions:
            return ("unknown", 0.0)
        
        # Map extensions to languages
        lang_map = {
            '.py': 'python',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java'
        }
        
        # Find most common
        most_common = max(extensions.items(), key=lambda x: x[1])
        language = lang_map.get(most_common[0], 'unknown')
        confidence = most_common[1] / sum(extensions.values())
        
        return (language, confidence)
    
    def create_orchestration_session(
        self, 
        project_id: str, 
        description: str,
        component_name: Optional[str] = None,
        max_parallel_agents: int = 3
    ) -> str:
        """
        Create a new orchestration session.
        
        Returns:
            Session ID
        """
        session_id = self._generate_id("ORCH")
        
        self.conn.execute(
            """
            INSERT INTO orchestration_sessions 
            (id, project_id, component_name, description, max_parallel_agents, status)
            VALUES (?, ?, ?, ?, ?, 'active')
            """,
            (session_id, project_id, component_name, description, max_parallel_agents)
        )
        self.conn.commit()
        
        # Detect and cache project language
        project = self._get_project(project_id)
        if project and project.get('repository'):
            lang, confidence = self.detect_project_language(project['repository'])
            self._cache_project_language(project_id, lang, confidence)
        
        return session_id
    
    def create_wave(
        self, 
        orchestration_id: str, 
        wave_number: int
    ) -> str:
        """
        Create a new wave for an orchestration session.
        
        Returns:
            Wave ID
        """
        wave_id = self._generate_id("WAVE")
        
        self.conn.execute(
            """
            INSERT INTO waves (id, orchestration_id, wave_number, status)
            VALUES (?, ?, ?, 'pending')
            """,
            (wave_id, orchestration_id, wave_number)
        )
        self.conn.commit()
        
        return wave_id
    
    def create_agent_session(
        self,
        orchestration_id: str,
        wave_id: str,
        agent_name: str,
        agent_type: str,
        task_description: str
    ) -> str:
        """
        Register an agent session.
        
        Returns:
            Agent session ID
        """
        session_id = self._generate_id("AGENT")
        
        self.conn.execute(
            """
            INSERT INTO agent_sessions 
            (id, orchestration_id, wave_id, agent_name, agent_type, task_description, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            """,
            (session_id, orchestration_id, wave_id, agent_name, agent_type, task_description)
        )
        self.conn.commit()
        
        return session_id
    
    def start_agent_session(self, session_id: str):
        """Mark agent session as started."""
        self.conn.execute(
            "UPDATE agent_sessions SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?",
            (session_id,)
        )
        self.conn.commit()
    
    def complete_agent_session(
        self, 
        session_id: str, 
        artifacts: Optional[Dict] = None
    ):
        """Mark agent session as completed with artifacts."""
        artifacts_json = json.dumps(artifacts) if artifacts else None
        
        self.conn.execute(
            """
            UPDATE agent_sessions 
            SET status = 'completed', 
                completed_at = CURRENT_TIMESTAMP,
                artifacts_json = ?
            WHERE id = ?
            """,
            (artifacts_json, session_id)
        )
        self.conn.commit()
    
    def add_dependency(self, task_id: str, depends_on_task_id: str):
        """Add a dependency between tasks."""
        self.conn.execute(
            "INSERT OR IGNORE INTO task_dependencies (task_id, depends_on_task_id) VALUES (?, ?)",
            (task_id, depends_on_task_id)
        )
        self.conn.commit()
    
    def start_wave(self, wave_id: str):
        """Mark wave as started."""
        self.conn.execute(
            "UPDATE waves SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?",
            (wave_id,)
        )
        self.conn.commit()
    
    def complete_wave(self, wave_id: str, synthesis_summary: str):
        """Mark wave as completed with synthesis."""
        self.conn.execute(
            """
            UPDATE waves 
            SET status = 'completed', 
                completed_at = CURRENT_TIMESTAMP,
                synthesis_summary = ?
            WHERE id = ?
            """,
            (synthesis_summary, wave_id)
        )
        self.conn.commit()
    
    def store_interface_contract(
        self,
        session_id: str,
        agent_id: str,
        contract_type: str,
        contract_name: str,
        language: str,
        definition: Dict,
        source_file: Optional[str] = None
    ) -> str:
        """
        Store an interface contract.
        
        Returns:
            Contract ID
        """
        contract_id = self._generate_id("CONTRACT")
        definition_json = json.dumps(definition)
        
        self.conn.execute(
            """
            INSERT INTO interface_contracts 
            (id, session_id, agent_id, contract_type, contract_name, language, definition_json, source_file)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (contract_id, session_id, agent_id, contract_type, contract_name, language, definition_json, source_file)
        )
        self.conn.commit()
        
        return contract_id
    
    def get_wave_contracts(self, wave_id: str) -> List[InterfaceContract]:
        """Get all contracts from agents in a wave."""
        cursor = self.conn.execute(
            """
            SELECT c.* FROM interface_contracts c
            JOIN agent_sessions a ON c.agent_id = a.id
            WHERE a.wave_id = ?
            """,
            (wave_id,)
        )
        
        contracts = []
        for row in cursor.fetchall():
            contracts.append(InterfaceContract(
                id=row['id'],
                session_id=row['session_id'],
                agent_id=row['agent_id'],
                contract_type=row['contract_type'],
                contract_name=row['contract_name'],
                language=row['language'],
                definition_json=row['definition_json'],
                source_file=row['source_file'],
                extracted_at=row['extracted_at']
            ))
        
        return contracts
    
    def record_contract_mismatch(
        self,
        orchestration_id: str,
        wave_id: str,
        contract_a_id: str,
        contract_b_id: str,
        mismatch_type: str,
        details: str
    ) -> str:
        """
        Record a contract mismatch.
        
        Returns:
            Mismatch ID
        """
        mismatch_id = self._generate_id("MISMATCH")
        
        self.conn.execute(
            """
            INSERT INTO contract_mismatches 
            (id, orchestration_id, wave_id, contract_a_id, contract_b_id, mismatch_type, details, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'detected')
            """,
            (mismatch_id, orchestration_id, wave_id, contract_a_id, contract_b_id, mismatch_type, details)
        )
        self.conn.commit()
        
        return mismatch_id
    
    def assign_fix_agent(self, mismatch_id: str, fix_agent_id: str):
        """Assign an agent to fix a mismatch."""
        self.conn.execute(
            """
            UPDATE contract_mismatches 
            SET fix_agent_id = ?, status = 'fixing', fix_attempts = fix_attempts + 1
            WHERE id = ?
            """,
            (fix_agent_id, mismatch_id)
        )
        self.conn.commit()
    
    def resolve_mismatch(self, mismatch_id: str):
        """Mark a mismatch as resolved."""
        self.conn.execute(
            """
            UPDATE contract_mismatches 
            SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (mismatch_id,)
        )
        self.conn.commit()
    
    def get_unresolved_mismatches(self, wave_id: str) -> List[Dict]:
        """Get all unresolved mismatches for a wave."""
        cursor = self.conn.execute(
            """
            SELECT * FROM contract_mismatches 
            WHERE wave_id = ? AND status != 'resolved'
            """,
            (wave_id,)
        )
        return self._rows_to_dicts(cursor.fetchall())
    
    def get_project_language(self, project_id: str) -> str:
        """Get cached project language or detect it."""
        cursor = self.conn.execute(
            "SELECT detected_language FROM project_languages WHERE project_id = ?",
            (project_id,)
        )
        row = cursor.fetchone()
        
        if row:
            return row['detected_language']
        
        # Detect and cache
        project = self._get_project(project_id)
        if project and project.get('repository'):
            lang, confidence = self.detect_project_language(project['repository'])
            self._cache_project_language(project_id, lang, confidence)
            return lang
        
        return 'unknown'
    
    def _get_project(self, project_id: str) -> Optional[Dict]:
        """Get project by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM projects WHERE id = ?",
            (project_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def _cache_project_language(self, project_id: str, language: str, confidence: float):
        """Cache detected project language."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO project_languages 
            (project_id, detected_language, detection_confidence, detected_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (project_id, language, confidence)
        )
        self.conn.commit()
    
    def get_wave_agents(self, wave_id: str) -> List[Dict]:
        """Get all agents in a wave."""
        cursor = self.conn.execute(
            "SELECT * FROM agent_sessions WHERE wave_id = ? ORDER BY started_at",
            (wave_id,)
        )
        return self._rows_to_dicts(cursor.fetchall())
    
    def get_ready_agents(self, wave_id: str) -> List[Dict]:
        """Get agents in a wave with no unmet dependencies."""
        cursor = self.conn.execute(
            """
            SELECT a.* FROM agent_sessions a
            WHERE a.wave_id = ? AND a.status = 'pending'
            AND NOT EXISTS (
                SELECT 1 FROM task_dependencies d
                JOIN agent_sessions dep ON d.depends_on_task_id = dep.id
                WHERE d.task_id = a.id AND dep.status != 'completed'
            )
            """,
            (wave_id,)
        )
        return self._rows_to_dicts(cursor.fetchall())
    
    def get_running_agents_count(self, wave_id: str) -> int:
        """Count currently running agents in a wave."""
        cursor = self.conn.execute(
            "SELECT COUNT(*) FROM agent_sessions WHERE wave_id = ? AND status = 'running'",
            (wave_id,)
        )
        return cursor.fetchone()[0]
    
    def is_wave_complete(self, wave_id: str) -> bool:
        """Check if all agents in a wave are completed."""
        cursor = self.conn.execute(
            """
            SELECT COUNT(*) FROM agent_sessions 
            WHERE wave_id = ? AND status NOT IN ('completed', 'failed')
            """,
            (wave_id,)
        )
        return cursor.fetchone()[0] == 0
    
    def complete_orchestration(self, orchestration_id: str):
        """Mark orchestration session as completed."""
        self.conn.execute(
            """
            UPDATE orchestration_sessions 
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (orchestration_id,)
        )
        self.conn.commit()


def main():
    """CLI interface for orchestration commands."""
    if len(sys.argv) < 2:
        print("Usage: orchestration.py <command> [args...]")
        print("Commands:")
        print("  create-session <project_id> <description> [--component=X] [--max-agents=N]")
        print("  create-wave <orchestration_id> <wave_number>")
        print("  create-agent <orchestration_id> <wave_id> <agent_name> <agent_type> <task>")
        print("  start-agent <agent_id>")
        print("  complete-agent <agent_id> [--artifacts=JSON]")
        print("  store-contract <session_id> <agent_id> <type> <name> <language> <definition_json> [source_file]")
        print("  validate-wave <wave_id> <orchestration_id> <project_id>")
        print("  detect-language <project_path>")
        print("  get-wave-agents <wave_id>")
        print("  get-session-status <session_id>")
        print("  get-mismatches <wave_id>")
        print("  get-contracts <wave_id>")
        print("  is-wave-complete <wave_id>")
        print("  complete-wave <wave_id> <summary>")
        print("  complete-orchestration <session_id>")
        print("  assign-fix-agent <mismatch_id> <fix_agent_id>")
        print("  resolve-mismatch <mismatch_id>")
        sys.exit(1)
    
    command = sys.argv[1]
    
    with OrchestrationManager() as om:
        if command == "detect-language":
            if len(sys.argv) < 3:
                print("Error: project_path required")
                sys.exit(1)
            lang, confidence = om.detect_project_language(sys.argv[2])
            print(json.dumps({"language": lang, "confidence": confidence}))
        
        elif command == "create-session":
            if len(sys.argv) < 4:
                print("Error: project_id and description required")
                sys.exit(1)
            
            project_id = sys.argv[2]
            description = sys.argv[3]
            
            # Parse optional args
            component = None
            max_agents = 3
            for arg in sys.argv[4:]:
                if arg.startswith("--component="):
                    component = arg.split("=", 1)[1]
                elif arg.startswith("--max-agents="):
                    max_agents = int(arg.split("=", 1)[1])
            
            session_id = om.create_orchestration_session(
                project_id, description, component, max_agents
            )
            print(json.dumps({"session_id": session_id}))
        
        elif command == "create-wave":
            if len(sys.argv) < 4:
                print("Error: orchestration_id and wave_number required")
                sys.exit(1)
            
            orchestration_id = sys.argv[2]
            wave_number = int(sys.argv[3])
            wave_id = om.create_wave(orchestration_id, wave_number)
            print(json.dumps({"wave_id": wave_id}))
        
        elif command == "create-agent":
            if len(sys.argv) < 7:
                print("Error: orchestration_id, wave_id, agent_name, agent_type, task required")
                sys.exit(1)
            
            orchestration_id = sys.argv[2]
            wave_id = sys.argv[3]
            agent_name = sys.argv[4]
            agent_type = sys.argv[5]
            task_description = sys.argv[6]
            
            agent_id = om.create_agent_session(
                orchestration_id, wave_id, agent_name, agent_type, task_description
            )
            print(json.dumps({"agent_id": agent_id}))
        
        elif command == "start-agent":
            if len(sys.argv) < 3:
                print("Error: agent_id required")
                sys.exit(1)
            om.start_agent_session(sys.argv[2])
            print(json.dumps({"status": "started"}))
        
        elif command == "complete-agent":
            if len(sys.argv) < 3:
                print("Error: agent_id required")
                sys.exit(1)
            
            agent_id = sys.argv[2]
            artifacts = None
            
            for arg in sys.argv[3:]:
                if arg.startswith("--artifacts="):
                    artifacts = json.loads(arg.split("=", 1)[1])
            
            om.complete_agent_session(agent_id, artifacts)
            print(json.dumps({"status": "completed"}))
        
        elif command == "store-contract":
            if len(sys.argv) < 8:
                print("Error: session_id, agent_id, type, name, language, definition_json required")
                sys.exit(1)
            
            session_id = sys.argv[2]
            agent_id = sys.argv[3]
            contract_type = sys.argv[4]
            contract_name = sys.argv[5]
            language = sys.argv[6]
            definition_json = sys.argv[7]
            source_file = sys.argv[8] if len(sys.argv) > 8 else None
            
            contract_id = om.store_interface_contract(
                session_id, agent_id, contract_type, contract_name, 
                language, json.loads(definition_json), source_file
            )
            print(json.dumps({"contract_id": contract_id}))
        
        elif command == "validate-wave":
            if len(sys.argv) < 5:
                print("Error: wave_id, orchestration_id, project_id required")
                sys.exit(1)
            
            wave_id = sys.argv[2]
            orchestration_id = sys.argv[3]
            project_id = sys.argv[4]
            
            # Get project language
            primary_language = om.get_project_language(project_id)
            
            # Get contracts from this wave
            contracts = om.get_wave_contracts(wave_id)
            
            # Group contracts by name
            by_name = {}
            for contract in contracts:
                if contract.contract_name not in by_name:
                    by_name[contract.contract_name] = []
                by_name[contract.contract_name].append(contract)
            
            # Find mismatches
            mismatches = []
            for name, contract_list in by_name.items():
                if len(contract_list) > 1:
                    # Compare contracts
                    for i, contract_a in enumerate(contract_list):
                        for contract_b in contract_list[i+1:]:
                            def_a = json.loads(contract_a.definition_json)
                            def_b = json.loads(contract_b.definition_json)
                            
                            if def_a != def_b:
                                # Determine which should win based on language
                                authoritative = contract_a if contract_a.language == primary_language else contract_b
                                other = contract_b if authoritative == contract_a else contract_a
                                
                                mismatch_id = om.record_contract_mismatch(
                                    orchestration_id,
                                    wave_id,
                                    contract_a.id,
                                    contract_b.id,
                                    "definition_mismatch",
                                    f"Contract '{name}' differs between {contract_a.language} and {contract_b.language}"
                                )
                                
                                mismatches.append({
                                    "mismatch_id": mismatch_id,
                                    "contract_name": name,
                                    "authoritative_language": primary_language,
                                    "needs_fix": True
                                })
            
            print(json.dumps({
                "contracts_found": len(contracts),
                "mismatches": mismatches,
                "primary_language": primary_language
            }))
        
        elif command == "get-wave-agents":
            if len(sys.argv) < 3:
                print("Error: wave_id required")
                sys.exit(1)
            wave_id = sys.argv[2]
            agents = om.get_wave_agents(wave_id)
            print(json.dumps({"agents": agents}))
        
        elif command == "get-session-status":
            if len(sys.argv) < 3:
                print("Error: session_id required")
                sys.exit(1)
            session_id = sys.argv[2]
            
            # Get session info
            cursor = om.conn.execute(
                "SELECT * FROM orchestration_sessions WHERE id = ?",
                (session_id,)
            )
            session = dict(cursor.fetchone()) if cursor.fetchone() else None
            
            # Get waves
            cursor = om.conn.execute(
                "SELECT * FROM waves WHERE orchestration_id = ? ORDER BY wave_number",
                (session_id,)
            )
            waves = om._rows_to_dicts(cursor.fetchall())
            
            print(json.dumps({
                "session": session,
                "waves": waves
            }))
        
        elif command == "get-mismatches":
            if len(sys.argv) < 3:
                print("Error: wave_id required")
                sys.exit(1)
            wave_id = sys.argv[2]
            mismatches = om.get_unresolved_mismatches(wave_id)
            print(json.dumps({"mismatches": mismatches}))
        
        elif command == "get-contracts":
            if len(sys.argv) < 3:
                print("Error: wave_id required")
                sys.exit(1)
            wave_id = sys.argv[2]
            contracts = om.get_wave_contracts(wave_id)
            print(json.dumps({
                "contracts": [
                    {
                        "id": c.id,
                        "name": c.contract_name,
                        "type": c.contract_type,
                        "language": c.language,
                        "definition": json.loads(c.definition_json)
                    }
                    for c in contracts
                ]
            }))
        
        elif command == "is-wave-complete":
            if len(sys.argv) < 3:
                print("Error: wave_id required")
                sys.exit(1)
            wave_id = sys.argv[2]
            is_complete = om.is_wave_complete(wave_id)
            print(json.dumps({"is_complete": is_complete}))
        
        elif command == "complete-wave":
            if len(sys.argv) < 4:
                print("Error: wave_id and summary required")
                sys.exit(1)
            wave_id = sys.argv[2]
            summary = sys.argv[3]
            om.complete_wave(wave_id, summary)
            print(json.dumps({"status": "completed"}))
        
        elif command == "complete-orchestration":
            if len(sys.argv) < 3:
                print("Error: session_id required")
                sys.exit(1)
            session_id = sys.argv[2]
            om.complete_orchestration(session_id)
            print(json.dumps({"status": "completed"}))
        
        elif command == "assign-fix-agent":
            if len(sys.argv) < 4:
                print("Error: mismatch_id and fix_agent_id required")
                sys.exit(1)
            mismatch_id = sys.argv[2]
            fix_agent_id = sys.argv[3]
            om.assign_fix_agent(mismatch_id, fix_agent_id)
            print(json.dumps({"status": "assigned"}))
        
        elif command == "resolve-mismatch":
            if len(sys.argv) < 3:
                print("Error: mismatch_id required")
                sys.exit(1)
            mismatch_id = sys.argv[2]
            om.resolve_mismatch(mismatch_id)
            print(json.dumps({"status": "resolved"}))
        
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)


if __name__ == "__main__":
    main()