"""
State management and data access layer
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from audit_orchestrator.config import Settings
from audit_orchestrator.core.db import Database, json_deserialize, json_serialize, row_to_dict, rows_to_list
from audit_orchestrator.core.errors import ProjectNotFoundError, ServiceNotFoundError, TargetNotFoundError


class AuditStore:
    """Main store for audit orchestration state"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.db = Database(settings.db_path)
    
    def _utc_now(self) -> str:
        """Get current UTC timestamp as ISO string"""
        return datetime.utcnow().isoformat()
    
    def _new_id(self) -> str:
        """Generate a new UUID"""
        return str(uuid.uuid4())
    
    # ===== Projects =====
    
    def create_project(
        self,
        base_path: str,
        input_file: str,
        profile: str = "default_blackbox",
        execution_mode: str = "type_1_no_llm",
    ) -> dict[str, Any]:
        """Create a new audit project"""
        project_id = self._new_id()
        now = self._utc_now()
        
        # Validate execution_mode
        valid_modes = ["type_1_no_llm", "type_2_post_host_llm", "type_3_interactive_llm"]
        if execution_mode not in valid_modes:
            raise ValueError(f"Invalid execution_mode: {execution_mode}. Valid modes: {valid_modes}")
        
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO projects (
                    project_id, base_path, input_file, profile, execution_mode,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, base_path, input_file, profile, execution_mode,
                "running", now, now
            ))
        
        return {
            "project_id": project_id,
            "base_path": base_path,
            "input_file": input_file,
            "profile": profile,
            "execution_mode": execution_mode,
            "status": "running",
            "created_at": now
        }
    
    def get_project(self, project_id: str) -> dict[str, Any]:
        """Get project by ID"""
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM projects WHERE project_id = ?",
                (project_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise ProjectNotFoundError(project_id)
            return row_to_dict(row)
    
    def get_project_by_path(self, base_path: str, input_file: str = "open_ports.txt") -> dict[str, Any]:
        """Get project by base_path and input_file"""
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM projects WHERE base_path = ? AND input_file = ? ORDER BY created_at DESC LIMIT 1",
                (base_path, input_file)
            )
            row = cursor.fetchone()
            if not row:
                raise ProjectNotFoundError(f"No project found at {base_path}")
            return row_to_dict(row)
    
    def update_project_status(
        self,
        project_id: str,
        status: str,
    ) -> None:
        """Update project status"""
        now = self._utc_now()
        with self.db.transaction() as conn:
            updates = {"status": status, "updated_at": now}
            if status == "completed":
                updates["completed_at"] = now
            
            set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
            values = list(updates.values()) + [project_id]
            
            conn.execute(
                f"UPDATE projects SET {set_clause} WHERE project_id = ?",
                values
            )
    
    def list_projects(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[dict[str, Any]]:
        """List projects with optional filtering"""
        with self.db.connection() as conn:
            if status:
                cursor = conn.execute(
                    "SELECT * FROM projects WHERE status = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (status, limit, offset)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM projects ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset)
                )
            return rows_to_list(cursor.fetchall())
    
    def reset_project_status(self, project_id: str) -> dict[str, Any]:
        """
        Reset all targets and services in a project to 'pending' status.
        
        This allows restarting an audit from scratch without losing
        the project structure.
        
        Returns counts of reset items.
        """
        with self.db.transaction() as conn:
            # Reset all targets to pending
            conn.execute("""
                UPDATE targets 
                SET status = 'pending', started_at = NULL, completed_at = NULL, error = NULL
                WHERE project_id = ?
            """, (project_id,))
            targets_reset = conn.execute("SELECT changes()").fetchone()[0]
            
            # Get all target_ids for this project
            cursor = conn.execute(
                "SELECT target_id FROM targets WHERE project_id = ?",
                (project_id,)
            )
            target_ids = [row["target_id"] for row in cursor.fetchall()]
            
            # Reset all services to pending
            services_reset = 0
            for target_id in target_ids:
                conn.execute("""
                    UPDATE services 
                    SET status = 'pending', started_at = NULL, completed_at = NULL, error = NULL
                    WHERE target_id = ?
                """, (target_id,))
                services_reset += conn.execute("SELECT changes()").fetchone()[0]
            
            # Reset all tasks to pending
            tasks_reset = 0
            for target_id in target_ids:
                cursor = conn.execute(
                    "SELECT service_id FROM services WHERE target_id = ?",
                    (target_id,)
                )
                service_ids = [row["service_id"] for row in cursor.fetchall()]
                
                for service_id in service_ids:
                    conn.execute("""
                        UPDATE audit_tasks 
                        SET status = 'pending', started_at = NULL, completed_at = NULL, 
                            duration_seconds = NULL, error = NULL, retry_count = 0
                        WHERE service_id = ?
                    """, (service_id,))
                    tasks_reset += conn.execute("SELECT changes()").fetchone()[0]
            
            # Update project status
            conn.execute("""
                UPDATE projects 
                SET status = 'running', completed_at = NULL, updated_at = ?
                WHERE project_id = ?
            """, (self._utc_now(), project_id))
        
        return {
            "project_id": project_id,
            "targets_reset": targets_reset,
            "services_reset": services_reset,
            "tasks_reset": tasks_reset,
            "status": "reset_complete"
        }
    
    def delete_project(self, project_id: str) -> None:
        """
        Delete a project and all related data (cascade).
        
        Deletes:
        - All findings for this project
        - All audit tasks for services in this project
        - All bitacora entries
        - All services for targets in this project
        - All targets in this project
        - The project itself
        """
        with self.db.transaction() as conn:
            # Get all targets for this project
            cursor = conn.execute(
                "SELECT target_id FROM targets WHERE project_id = ?",
                (project_id,)
            )
            target_ids = [row["target_id"] for row in cursor.fetchall()]
            
            # Delete findings
            conn.execute(
                "DELETE FROM findings WHERE project_id = ?",
                (project_id,)
            )
            
            # Delete bitacora entries
            conn.execute(
                "DELETE FROM bitacora_entries WHERE project_id = ?",
                (project_id,)
            )
            
            # For each target, delete services and their tasks
            for target_id in target_ids:
                # Get all services for this target
                cursor = conn.execute(
                    "SELECT service_id FROM services WHERE target_id = ?",
                    (target_id,)
                )
                service_ids = [row["service_id"] for row in cursor.fetchall()]
                
                # Delete audit tasks for each service
                for service_id in service_ids:
                    conn.execute(
                        "DELETE FROM audit_tasks WHERE service_id = ?",
                        (service_id,)
                    )
                
                # Delete services
                conn.execute(
                    "DELETE FROM services WHERE target_id = ?",
                    (target_id,)
                )
            
            # Delete targets
            conn.execute(
                "DELETE FROM targets WHERE project_id = ?",
                (project_id,)
            )
            
            # Delete project
            conn.execute(
                "DELETE FROM projects WHERE project_id = ?",
                (project_id,)
            )
    
    # ===== Targets =====
    
    def create_target(
        self,
        project_id: str,
        ip_or_hostname: str,
        work_dir: str,
        ports: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Create a new target"""
        target_id = self._new_id()
        
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO targets (
                    target_id, project_id, ip_or_hostname, work_dir,
                    status, ports_detected
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                target_id, project_id, ip_or_hostname, work_dir,
                "pending", json_serialize(ports)
            ))
        
        return {
            "target_id": target_id,
            "project_id": project_id,
            "ip_or_hostname": ip_or_hostname,
            "work_dir": work_dir,
            "status": "pending",
            "ports": ports
        }
    
    def get_target(self, target_id: str) -> dict[str, Any]:
        """Get target by ID"""
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM targets WHERE target_id = ?",
                (target_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise TargetNotFoundError(target_id)
            
            data = row_to_dict(row)
            data["ports"] = json_deserialize(data.get("ports_detected"))
            return data
    
    def update_target_status(
        self,
        target_id: str,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """Update target status"""
        now = self._utc_now()
        with self.db.transaction() as conn:
            if status in ("auditing",) and not self._get_target_started_at(conn, target_id):
                conn.execute(
                    "UPDATE targets SET status = ?, started_at = ? WHERE target_id = ?",
                    (status, now, target_id)
                )
            elif status in ("completed", "failed"):
                conn.execute(
                    "UPDATE targets SET status = ?, completed_at = ?, error = ? WHERE target_id = ?",
                    (status, now, error, target_id)
                )
            else:
                conn.execute(
                    "UPDATE targets SET status = ? WHERE target_id = ?",
                    (status, target_id)
                )
    
    def _get_target_started_at(self, conn, target_id: str) -> Optional[str]:
        """Helper to check if target has started_at"""
        cursor = conn.execute(
            "SELECT started_at FROM targets WHERE target_id = ?",
            (target_id,)
        )
        row = cursor.fetchone()
        return row["started_at"] if row else None
    
    def get_targets_by_project(
        self,
        project_id: str,
        status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Get all targets for a project"""
        with self.db.connection() as conn:
            if status:
                cursor = conn.execute(
                    "SELECT * FROM targets WHERE project_id = ? AND status = ?",
                    (project_id, status)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM targets WHERE project_id = ?",
                    (project_id,)
                )
            
            results = []
            for row in cursor.fetchall():
                data = row_to_dict(row)
                data["ports"] = json_deserialize(data.get("ports_detected"))
                results.append(data)
            return results
    
    def get_next_pending_target(self, project_id: str) -> Optional[dict[str, Any]]:
        """Get next pending or auditing target"""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM targets 
                WHERE project_id = ? AND status IN ('pending', 'auditing')
                ORDER BY started_at ASC NULLS FIRST
                LIMIT 1
            """, (project_id,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            data = row_to_dict(row)
            data["ports"] = json_deserialize(data.get("ports_detected"))
            return data
    
    def get_all_pending_targets(self, project_id: str) -> list[dict[str, Any]]:
        """Pending hosts, plus hosts left in auditing by an interrupted run."""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM targets
                WHERE project_id = ?
                AND status IN ('pending', 'auditing')
                ORDER BY CASE status WHEN 'auditing' THEN 0 ELSE 1 END, started_at
            """, (project_id,))
            
            rows = cursor.fetchall()
            targets = []
            for row in rows:
                data = row_to_dict(row)
                data["ports"] = json_deserialize(data.get("ports_detected"))
                targets.append(data)
            return targets
    
    # ===== Services =====
    
    def create_service(
        self,
        target_id: str,
        port: int,
        protocol: str,
        service_name: Optional[str] = None,
        max_time_seconds: int = 900,
        version: Optional[str] = None
    ) -> dict[str, Any]:
        """Create a new service"""
        service_id = self._new_id()
        
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO services (
                    service_id, target_id, port, protocol, service_name,
                    version, status, max_time_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                service_id, target_id, port, protocol, service_name,
                version, "pending", max_time_seconds
            ))
        
        return {
            "service_id": service_id,
            "target_id": target_id,
            "port": port,
            "protocol": protocol,
            "service_name": service_name,
            "version": version,
            "status": "pending",
            "max_time_seconds": max_time_seconds
        }
    
    def get_service(self, service_id: str) -> dict[str, Any]:
        """Get service by ID"""
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM services WHERE service_id = ?",
                (service_id,)
            )
            row = cursor.fetchone()
            if not row:
                raise ServiceNotFoundError(service_id)
            return row_to_dict(row)
    
    def update_service_status(
        self,
        service_id: str,
        status: str,
        error: Optional[str] = None
    ) -> None:
        """Update service status"""
        now = self._utc_now()
        with self.db.transaction() as conn:
            if status == "running":
                conn.execute(
                    "UPDATE services SET status = ?, started_at = ? WHERE service_id = ?",
                    (status, now, service_id)
                )
            elif status in ("completed", "timeout", "failed"):
                conn.execute(
                    "UPDATE services SET status = ?, completed_at = ?, error = ? WHERE service_id = ?",
                    (status, now, error, service_id)
                )
            else:
                conn.execute(
                    "UPDATE services SET status = ? WHERE service_id = ?",
                    (status, service_id)
                )
    
    def get_services_by_target(
        self,
        target_id: str,
        status: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Get all services for a target"""
        with self.db.connection() as conn:
            if status:
                cursor = conn.execute(
                    "SELECT * FROM services WHERE target_id = ? AND status = ?",
                    (target_id, status)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM services WHERE target_id = ?",
                    (target_id,)
                )
            return rows_to_list(cursor.fetchall())
    
    def get_next_pending_service(self, target_id: str) -> Optional[dict[str, Any]]:
        """Get next pending service for a target"""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM services 
                WHERE target_id = ? AND status = 'pending'
                ORDER BY port ASC
                LIMIT 1
            """, (target_id,))
            
            row = cursor.fetchone()
            return row_to_dict(row) if row else None
    
    # ===== Audit Tasks =====
    
    def create_task(
        self,
        service_id: str,
        task_type: str,
        kali_command: str
    ) -> dict[str, Any]:
        """Create a new audit task"""
        task_id = self._new_id()
        
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO audit_tasks (
                    task_id, service_id, task_type, kali_command, status
                ) VALUES (?, ?, ?, ?, ?)
            """, (task_id, service_id, task_type, kali_command, "pending"))
        
        return {
            "task_id": task_id,
            "service_id": service_id,
            "task_type": task_type,
            "kali_command": kali_command,
            "status": "pending"
        }
    
    def update_task_status(
        self,
        task_id: str,
        status: str,
        output_path: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None
    ) -> None:
        """Update task status"""
        now = self._utc_now()
        with self.db.transaction() as conn:
            if status == "running":
                conn.execute(
                    "UPDATE audit_tasks SET status = ?, started_at = ? WHERE task_id = ?",
                    (status, now, task_id)
                )
            elif status in ("completed", "failed", "skipped"):
                conn.execute("""
                    UPDATE audit_tasks 
                    SET status = ?, completed_at = ?, output_path = ?, 
                        duration_seconds = ?, error = ?
                    WHERE task_id = ?
                """, (status, now, output_path, duration_seconds, error, task_id))
    
    def increment_task_retry(self, task_id: str) -> int:
        """Increment retry count and return new value"""
        with self.db.transaction() as conn:
            cursor = conn.execute(
                "SELECT retry_count FROM audit_tasks WHERE task_id = ?",
                (task_id,)
            )
            row = cursor.fetchone()
            retry_count = (row["retry_count"] if row else 0) + 1
            
            conn.execute(
                "UPDATE audit_tasks SET retry_count = ? WHERE task_id = ?",
                (retry_count, task_id)
            )
            
            return retry_count
    
    def get_tasks_by_service(self, service_id: str) -> list[dict[str, Any]]:
        """Get all tasks for a service"""
        with self.db.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM audit_tasks WHERE service_id = ? ORDER BY started_at",
                (service_id,)
            )
            return rows_to_list(cursor.fetchall())

    def get_tasks_by_target(self, target_id: str) -> list[dict[str, Any]]:
        """Get every audit task that belongs to a target."""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT t.* FROM audit_tasks t
                JOIN services s ON t.service_id = s.service_id
                WHERE s.target_id = ?
                ORDER BY t.started_at
            """, (target_id,))
            return rows_to_list(cursor.fetchall())
    
    # ===== Bitacora (Audit Log) =====
    
    def log_bitacora(
        self,
        project_id: str,
        operation: str,
        result: str,
        target_id: Optional[str] = None,
        service_id: Optional[str] = None,
        command: Optional[str] = None,
        notes: Optional[str] = None
    ) -> str:
        """Add entry to bitacora"""
        entry_id = self._new_id()
        timestamp = self._utc_now()
        
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO bitacora_entries (
                    entry_id, project_id, target_id, service_id,
                    timestamp, operation, command, result, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry_id, project_id, target_id, service_id,
                timestamp, operation, command, result, notes
            ))
        
        return entry_id
    
    def get_bitacora_entries(
        self,
        project_id: str,
        target_id: Optional[str] = None,
        limit: int = 100
    ) -> list[dict[str, Any]]:
        """Get bitacora entries"""
        with self.db.connection() as conn:
            if target_id:
                cursor = conn.execute("""
                    SELECT * FROM bitacora_entries 
                    WHERE project_id = ? AND target_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (project_id, target_id, limit))
            else:
                cursor = conn.execute("""
                    SELECT * FROM bitacora_entries 
                    WHERE project_id = ?
                    ORDER BY timestamp DESC LIMIT ?
                """, (project_id, limit))
            
            return rows_to_list(cursor.fetchall())

    def get_bitacora_by_target(self, target_id: str, limit: int = 200) -> list[dict[str, Any]]:
        """Get bitacora entries for one target, oldest first."""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM bitacora_entries
                WHERE target_id = ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (target_id, limit))
            return rows_to_list(cursor.fetchall())
    
    def get_last_bitacora_entry(self, project_id: str) -> Optional[dict[str, Any]]:
        """Get the most recent bitacora entry"""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM bitacora_entries 
                WHERE project_id = ?
                ORDER BY timestamp DESC LIMIT 1
            """, (project_id,))
            
            row = cursor.fetchone()
            return row_to_dict(row) if row else None
    
    # ===== Findings =====
    
    def create_finding(
        self,
        project_id: str,
        target_id: str,
        severity: str,
        title: str,
        service_id: Optional[str] = None,
        description: Optional[str] = None,
        evidence_path: Optional[str] = None,
        exploit_available: bool = False,
        cwe: Optional[str] = None,
        cvss_score: Optional[float] = None
    ) -> dict[str, Any]:
        """Create a new finding"""
        finding_id = self._new_id()
        now = self._utc_now()
        
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO findings (
                    finding_id, project_id, target_id, service_id,
                    severity, title, description, evidence_path,
                    exploit_available, cwe, cvss_score, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                finding_id, project_id, target_id, service_id,
                severity, title, description, evidence_path,
                1 if exploit_available else 0, cwe, cvss_score, now
            ))
        
        return {
            "finding_id": finding_id,
            "project_id": project_id,
            "target_id": target_id,
            "service_id": service_id,
            "severity": severity,
            "title": title,
            "description": description,
            "evidence_path": evidence_path,
            "exploit_available": exploit_available,
            "cwe": cwe,
            "cvss_score": cvss_score,
            "created_at": now
        }
    
    def get_findings_by_project(
        self,
        project_id: str,
        severity: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Get all findings for a project"""
        with self.db.connection() as conn:
            if severity:
                cursor = conn.execute("""
                    SELECT * FROM findings 
                    WHERE project_id = ? AND severity = ?
                    ORDER BY created_at DESC
                """, (project_id, severity))
            else:
                cursor = conn.execute("""
                    SELECT * FROM findings 
                    WHERE project_id = ?
                    ORDER BY created_at DESC
                """, (project_id,))
            
            return rows_to_list(cursor.fetchall())

    def get_findings_by_target(self, target_id: str) -> list[dict[str, Any]]:
        """Get findings recorded for one target."""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM findings
                WHERE target_id = ?
                ORDER BY created_at DESC
            """, (target_id,))
            return rows_to_list(cursor.fetchall())
    
    def get_findings_count_by_severity(self, project_id: str) -> dict[str, int]:
        """Get count of findings grouped by severity"""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT severity, COUNT(*) as count
                FROM findings
                WHERE project_id = ?
                GROUP BY severity
            """, (project_id,))
            
            return {row["severity"]: row["count"] for row in cursor.fetchall()}
    
    # ===== Statistics =====
    
    def get_project_statistics(self, project_id: str) -> dict[str, Any]:
        """Get comprehensive project statistics"""
        with self.db.connection() as conn:
            # Target counts
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM targets
                WHERE project_id = ?
                GROUP BY status
            """, (project_id,))
            target_stats = {row["status"]: row["count"] for row in cursor.fetchall()}
            
            # Service counts
            cursor = conn.execute("""
                SELECT s.status, COUNT(*) as count
                FROM services s
                JOIN targets t ON s.target_id = t.target_id
                WHERE t.project_id = ?
                GROUP BY s.status
            """, (project_id,))
            service_stats = {row["status"]: row["count"] for row in cursor.fetchall()}
            
            # Total counts
            cursor = conn.execute("""
                SELECT COUNT(*) as total FROM targets WHERE project_id = ?
            """, (project_id,))
            total_targets = cursor.fetchone()["total"]
            
            cursor = conn.execute("""
                SELECT COUNT(*) as total
                FROM services s
                JOIN targets t ON s.target_id = t.target_id
                WHERE t.project_id = ?
            """, (project_id,))
            total_services = cursor.fetchone()["total"]
            
            # Findings
            findings_by_severity = self.get_findings_count_by_severity(project_id)
            
            return {
                "total_targets": total_targets,
                "targets_by_status": target_stats,
                "total_services": total_services,
                "services_by_status": service_stats,
                "findings_by_severity": findings_by_severity,
                "total_findings": sum(findings_by_severity.values())
            }
    
    # ===== LLM Execution State (Type 3) =====
    
    def create_llm_execution_state(
        self,
        project_id: str,
        target_id: str
    ) -> str:
        """Create execution state tracker for Type 3 LLM control"""
        state_id = self._new_id()
        now = self._utc_now()
        
        with self.db.transaction() as conn:
            conn.execute("""
                INSERT INTO llm_execution_state (
                    state_id, project_id, target_id, commands_executed,
                    execution_time_seconds, created_at, updated_at
                ) VALUES (?, ?, ?, 0, 0.0, ?, ?)
            """, (state_id, project_id, target_id, now, now))
        
        return state_id
    
    def get_llm_execution_state(
        self,
        project_id: str,
        target_id: str
    ) -> dict[str, Any]:
        """Get current execution state for Type 3"""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM llm_execution_state
                WHERE project_id = ? AND target_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (project_id, target_id))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"No LLM execution state found for project {project_id}, target {target_id}")
            return row_to_dict(row)
    
    def update_llm_execution_state(
        self,
        state_id: str,
        commands_executed: int,
        execution_time_seconds: float,
        last_command: Optional[str] = None,
        last_output: Optional[str] = None
    ) -> None:
        """Update execution state for Type 3"""
        now = self._utc_now()
        
        with self.db.transaction() as conn:
            conn.execute("""
                UPDATE llm_execution_state
                SET commands_executed = ?,
                    execution_time_seconds = ?,
                    last_command = ?,
                    last_output = ?,
                    updated_at = ?
                WHERE state_id = ?
            """, (
                commands_executed,
                execution_time_seconds,
                last_command,
                last_output,
                now,
                state_id
            ))
    
    def get_llm_execution_state_by_id(self, state_id: str) -> dict[str, Any]:
        """Get execution state by state_id"""
        with self.db.connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM llm_execution_state
                WHERE state_id = ?
            """, (state_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"No LLM execution state found with state_id {state_id}")
            return row_to_dict(row)
