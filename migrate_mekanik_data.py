#!/usr/bin/env python3
"""
Migrate data from mekanik PROJECT-MEMORY.json to unified SQLite memory database.
Uses simplified memory_entries table (v2.0 schema).
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path.home() / ".local" / "share" / "abby-normal" / "memory.db"
PROJECT_MEMORY_PATH = Path("/home/rhibbitts/code/python/mekanik/.worktrees/tiered-subscription-pricing/PROJECT-MEMORY.json")


def migrate_learnings(conn, learnings_list, project_id="mekanik", component="Backend"):
    """Migrate learnings from PROJECT-MEMORY.json to unified memory_entries."""
    learning_count = 0
    
    for idx, learning_text in enumerate(learnings_list, start=2):  # Start at 2 (LEARN-001 already exists)
        learning_id = f"LEARN-{idx:03d}"
        
        # Parse the learning text
        if " — " in learning_text:
            parts = learning_text.split(" — ", 1)
            title = parts[0].strip()
            content = parts[1].strip() if len(parts) > 1 else learning_text
        else:
            title = learning_text[:80] + "..." if len(learning_text) > 80 else learning_text
            content = learning_text
        
        # Build tags from content
        tags = []
        if "Python" in learning_text or "pytest" in learning_text:
            tags.append("Python")
        if "Flask" in learning_text:
            tags.append("Flask")
        if "Stripe" in learning_text:
            tags.append("Stripe")
        if "Vue" in learning_text or "frontend" in learning_text.lower():
            tags.extend(["Vue.js", "JavaScript", "Frontend"])
        if "test" in learning_text.lower():
            tags.append("Testing")
        if "security" in learning_text.lower():
            tags.append("Security")
        if "deployment" in learning_text.lower() or "zero-downtime" in learning_text.lower():
            tags.append("DevOps")
        if "API" in learning_text:
            tags.append("API Design")
        if "git" in learning_text.lower():
            tags.append("Git Workflow")
        if "subscription" in learning_text.lower() or "checkout" in learning_text.lower():
            tags.append("Payment Processing")
        if "UI" in learning_text or "UX" in learning_text:
            tags.append("UI/UX")
        if "database" in learning_text.lower():
            tags.append("Database Design")
        
        # Build metadata
        metadata = {
            "context": f"Learned during tiered subscription pricing implementation",
            "implementation": "",
            "source": "PROJECT-MEMORY.json",
            "tags": tags
        }
        
        conn.execute("""
            INSERT INTO memory_entries 
            (id, project_id, component_name, title, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            learning_id,
            project_id,
            component,
            title,
            content,
            json.dumps(metadata)
        ))
        learning_count += 1
    
    return learning_count


def migrate_decisions(conn, decisions_list, project_id="mekanik", component="Backend"):
    """Migrate decisions from PROJECT-MEMORY.json to unified memory_entries."""
    decision_count = 0
    
    for decision in decisions_list:
        # Build tags
        tags = ["Decision", "Critical"]
        if "subscription" in decision["decision"].lower():
            tags.append("SaaS Architecture")
        if "tier" in decision["decision"].lower():
            tags.append("Business Logic")
        
        metadata = {
            "rationale": decision["rationale"],
            "alternatives_considered": decision.get("alternatives_considered", []),
            "made_by": decision.get("made_by", "Unknown"),
            "outcome": decision.get("outcome", "Unknown"),
            "date": decision["date"],
            "source": "PROJECT-MEMORY.json",
            "tags": tags
        }
        
        conn.execute("""
            INSERT INTO memory_entries 
            (id, project_id, component_name, title, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            decision["id"],
            project_id,
            component,
            decision["decision"][:100],  # Truncate for title
            decision["decision"],
            json.dumps(metadata)
        ))
        decision_count += 1
    
    return decision_count


def migrate_architectural_decisions(conn, arch_decisions_list, project_id="mekanik"):
    """Migrate architectural decisions to unified memory_entries."""
    arch_count = 0
    
    for decision in arch_decisions_list:
        metadata = {
            "rationale": decision["rationale"],
            "details": decision.get("details", ""),
            "date": decision["date"],
            "scope": f"project:{project_id}",
            "source": "PROJECT-MEMORY.json",
            "tags": ["Architecture", "Project-Wide"]
        }
        
        conn.execute("""
            INSERT INTO memory_entries 
            (id, project_id, component_name, title, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            decision["id"],
            project_id,
            None,  # Project-wide
            f"[ARCH] {decision['decision'][:80]}",
            decision["decision"],
            json.dumps(metadata)
        ))
        arch_count += 1
    
    return arch_count


def migrate_changelog(conn, changelog_list, project_id="mekanik", component="Backend"):
    """Migrate changelog to unified memory_entries."""
    changelog_count = 0
    
    for entry in changelog_list:
        # Build content from changes
        content = "\n".join(entry.get("changes", []))
        if not content:
            content = f"Session: {entry.get('session', 'Unknown')}"
        
        metadata = {
            "author": entry.get("author", "Unknown"),
            "session": entry.get("session", ""),
            "changes": entry.get("changes", []),
            "date": entry["date"],
            "source": "PROJECT-MEMORY.json",
            "tags": ["Session", "History"]
        }
        
        conn.execute("""
            INSERT INTO memory_entries 
            (id, project_id, component_name, title, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            f"CHANGELOG-{entry['date']}",
            project_id,
            component,
            entry.get("session", f"Session {entry['date']}"),
            content,
            json.dumps(metadata)
        ))
        changelog_count += 1
    
    return changelog_count


def migrate_phases(conn, phases_list, project_id="mekanik"):
    """Migrate phases to unified memory_entries."""
    phase_count = 0
    
    for phase in phases_list:
        metadata = {
            "status": phase["status"],
            "started": phase["started"],
            "completed": phase.get("completed"),
            "deliverables": phase.get("deliverables", []),
            "source": "PROJECT-MEMORY.json",
            "tags": ["Phase", "Planning"]
        }
        
        conn.execute("""
            INSERT INTO memory_entries 
            (id, project_id, component_name, title, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            phase["id"],
            project_id,
            None,  # Project-wide
            phase["name"],
            phase.get("description", f"Phase: {phase['name']}"),
            json.dumps(metadata)
        ))
        phase_count += 1
    
    return phase_count


def migrate_open_questions(conn, questions_list, project_id="mekanik", component="Backend"):
    """Migrate open questions to unified memory_entries."""
    question_count = 0
    
    for idx, question_text in enumerate(questions_list, start=1):
        metadata = {
            "status": "open",
            "source": "PROJECT-MEMORY.json",
            "tags": ["Open Question", "TODO"]
        }
        
        conn.execute("""
            INSERT INTO memory_entries 
            (id, project_id, component_name, title, content, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            f"Q-{idx:03d}",
            project_id,
            component,
            question_text[:80] + "..." if len(question_text) > 80 else question_text,
            question_text,
            json.dumps(metadata)
        ))
        question_count += 1
    
    return question_count


def main():
    """Main migration function."""
    print(f"Loading PROJECT-MEMORY.json from {PROJECT_MEMORY_PATH}")
    
    with open(PROJECT_MEMORY_PATH) as f:
        data = json.load(f)
    
    conn = sqlite3.connect(DB_PATH)
    
    try:
        print("\nMigrating data to unified memory_entries table...")
        
        # Migrate learnings
        learnings_count = migrate_learnings(conn, data.get("learnings", []))
        print(f"✅ Migrated {learnings_count} learnings")
        
        # Migrate decisions
        decisions_count = migrate_decisions(conn, data.get("decisions", []))
        print(f"✅ Migrated {decisions_count} decisions")
        
        # Migrate architectural decisions
        arch_count = migrate_architectural_decisions(conn, data.get("architecture_decisions", []))
        print(f"✅ Migrated {arch_count} architectural decisions")
        
        # Migrate changelog
        changelog_count = migrate_changelog(conn, data.get("changelog", []))
        print(f"✅ Migrated {changelog_count} changelog entries")
        
        # Migrate phases
        phases_count = migrate_phases(conn, data.get("phases", []))
        print(f"✅ Migrated {phases_count} phases")
        
        # Migrate open questions
        questions_count = migrate_open_questions(conn, data.get("open_questions", []))
        print(f"✅ Migrated {questions_count} open questions")
        
        # Update project last_active date
        conn.execute("""
            UPDATE projects
            SET last_active = ?, current_phase = ?
            WHERE id = ?
        """, (
            data["project"]["current_date"],
            data["project"]["status"],
            "mekanik"
        ))
        print(f"✅ Updated mekanik project metadata")
        
        conn.commit()
        print("\n✅ Migration successful!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()