"""
SQLite database schema and operations
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional


class Database:
    """SQLite database manager"""
    
    SCHEMA_VERSION = 2
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_schema()
    
    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a transaction context"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def _ensure_schema(self) -> None:
        """Create or update database schema"""
        with self.transaction() as conn:
            # Create schema_version table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            
            # Check current version
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
            current_version = row[0] if row else 0
            
            if current_version < self.SCHEMA_VERSION:
                self._apply_migrations(conn, current_version)
    
    def _apply_migrations(self, conn: sqlite3.Connection, from_version: int) -> None:
        """Apply database migrations"""
        if from_version < 1:
            self._create_initial_schema(conn)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (1, datetime.utcnow().isoformat())
            )
        
        if from_version < 2:
            self._migrate_to_v2(conn)
            conn.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (2, datetime.utcnow().isoformat())
            )
    
    def _create_initial_schema(self, conn: sqlite3.Connection) -> None:
        """Create initial database schema"""
        
        # Projects table
        conn.execute("""
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                base_path TEXT NOT NULL,
                input_file TEXT NOT NULL,
                profile TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT
            )
        """)
        
        # Targets table (IPs/hostnames)
        conn.execute("""
            CREATE TABLE targets (
                target_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                ip_or_hostname TEXT NOT NULL,
                work_dir TEXT NOT NULL,
                status TEXT NOT NULL,
                ports_detected TEXT,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(project_id)
            )
        """)
        
        conn.execute("CREATE INDEX idx_targets_project ON targets(project_id)")
        conn.execute("CREATE INDEX idx_targets_status ON targets(status)")
        
        # Services table (ports per target)
        conn.execute("""
            CREATE TABLE services (
                service_id TEXT PRIMARY KEY,
                target_id TEXT NOT NULL,
                port INTEGER NOT NULL,
                protocol TEXT NOT NULL,
                service_name TEXT,
                status TEXT NOT NULL,
                max_time_seconds INTEGER NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error TEXT,
                FOREIGN KEY (target_id) REFERENCES targets(target_id)
            )
        """)
        
        conn.execute("CREATE INDEX idx_services_target ON services(target_id)")
        conn.execute("CREATE INDEX idx_services_status ON services(status)")
        
        # Audit tasks table
        conn.execute("""
            CREATE TABLE audit_tasks (
                task_id TEXT PRIMARY KEY,
                service_id TEXT NOT NULL,
                task_type TEXT NOT NULL,
                kali_command TEXT NOT NULL,
                status TEXT NOT NULL,
                output_path TEXT,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds REAL,
                error TEXT,
                retry_count INTEGER DEFAULT 0,
                FOREIGN KEY (service_id) REFERENCES services(service_id)
            )
        """)
        
        conn.execute("CREATE INDEX idx_tasks_service ON audit_tasks(service_id)")
        conn.execute("CREATE INDEX idx_tasks_status ON audit_tasks(status)")
        
        # Bitacora entries (audit log)
        conn.execute("""
            CREATE TABLE bitacora_entries (
                entry_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                target_id TEXT,
                service_id TEXT,
                timestamp TEXT NOT NULL,
                operation TEXT NOT NULL,
                command TEXT,
                result TEXT NOT NULL,
                notes TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(project_id),
                FOREIGN KEY (target_id) REFERENCES targets(target_id),
                FOREIGN KEY (service_id) REFERENCES services(service_id)
            )
        """)
        
        conn.execute("CREATE INDEX idx_bitacora_project ON bitacora_entries(project_id)")
        conn.execute("CREATE INDEX idx_bitacora_timestamp ON bitacora_entries(timestamp)")
        
        # Findings table
        conn.execute("""
            CREATE TABLE findings (
                finding_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                service_id TEXT,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                evidence_path TEXT,
                exploit_available INTEGER DEFAULT 0,
                cwe TEXT,
                cvss_score REAL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(project_id),
                FOREIGN KEY (target_id) REFERENCES targets(target_id),
                FOREIGN KEY (service_id) REFERENCES services(service_id)
            )
        """)
        
        conn.execute("CREATE INDEX idx_findings_project ON findings(project_id)")
        conn.execute("CREATE INDEX idx_findings_severity ON findings(severity)")
        conn.execute("CREATE INDEX idx_findings_target ON findings(target_id)")
    
    def _migrate_to_v2(self, conn: sqlite3.Connection) -> None:
        """Migrate database to version 2: Add LLM execution modes"""
        
        # Check if execution_mode column already exists
        cursor = conn.execute("PRAGMA table_info(projects)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "execution_mode" not in columns:
            # Add execution_mode column to projects table
            conn.execute("""
                ALTER TABLE projects
                ADD COLUMN execution_mode TEXT NOT NULL DEFAULT 'type_1_no_llm'
            """)
        
        # Check if llm_execution_state table already exists
        cursor = conn.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='llm_execution_state'
        """)
        
        if not cursor.fetchone():
            # Create llm_execution_state table for Type 3 tracking
            conn.execute("""
                CREATE TABLE llm_execution_state (
                    state_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    commands_executed INTEGER DEFAULT 0,
                    execution_time_seconds REAL DEFAULT 0.0,
                    last_command TEXT,
                    last_output TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (project_id) REFERENCES projects(project_id),
                    FOREIGN KEY (target_id) REFERENCES targets(target_id)
                )
            """)
            
            conn.execute("CREATE INDEX idx_llm_state_project ON llm_execution_state(project_id)")
            conn.execute("CREATE INDEX idx_llm_state_target ON llm_execution_state(target_id)")


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a SQLite row to a dictionary"""
    return {key: row[key] for key in row.keys()}


def rows_to_list(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert list of SQLite rows to list of dictionaries"""
    return [row_to_dict(row) for row in rows]


def json_serialize(obj: Any) -> str:
    """Serialize object to JSON string"""
    return json.dumps(obj, ensure_ascii=False)


def json_deserialize(s: Optional[str]) -> Any:
    """Deserialize JSON string to object"""
    if s is None:
        return None
    return json.loads(s)
