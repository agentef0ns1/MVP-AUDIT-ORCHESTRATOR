#!/usr/bin/env python3
"""
Script to reset a project's targets and services to 'pending' status.
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

def reset_project(project_id: str):
    """Reset all targets and services in a project to pending status"""
    
    db_path = Path.home() / ".local" / "share" / "audit-orchestrator" / "audit_state.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Check if project exists
        cursor.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
        project = cursor.fetchone()
        
        if not project:
            print(f"❌ Project not found: {project_id}")
            sys.exit(1)
        
        print(f"\n📊 Project: {project['base_path']}")
        print(f"   Status: {project['status']}")
        print(f"   Created: {project['created_at']}")
        
        # Get current statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'running' THEN 1 ELSE 0 END) as running,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM targets 
            WHERE project_id = ?
        """, (project_id,))
        targets_stats = cursor.fetchone()
        
        print(f"\n📍 Current Targets Status:")
        print(f"   Total: {targets_stats['total']}")
        print(f"   Pending: {targets_stats['pending']}")
        print(f"   Running: {targets_stats['running']}")
        print(f"   Completed: {targets_stats['completed']}")
        print(f"   Failed: {targets_stats['failed']}")
        
        # Get services stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN s.status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN s.status = 'running' THEN 1 ELSE 0 END) as running,
                SUM(CASE WHEN s.status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN s.status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM services s
            JOIN targets t ON s.target_id = t.target_id
            WHERE t.project_id = ?
        """, (project_id,))
        services_stats = cursor.fetchone()
        
        print(f"\n🔧 Current Services Status:")
        print(f"   Total: {services_stats['total']}")
        print(f"   Pending: {services_stats['pending']}")
        print(f"   Running: {services_stats['running']}")
        print(f"   Completed: {services_stats['completed']}")
        print(f"   Failed: {services_stats['failed']}")
        
        # Confirm reset
        print(f"\n⚠️  This will reset ALL targets and services to 'pending' status.")
        response = input("Continue? [y/N]: ")
        
        if response.lower() != 'y':
            print("❌ Aborted.")
            sys.exit(0)
        
        now = datetime.now(timezone.utc).isoformat()
        
        # Begin transaction
        cursor.execute("BEGIN TRANSACTION")
        
        # Reset targets
        cursor.execute("""
            UPDATE targets 
            SET status = 'pending', 
                started_at = NULL, 
                completed_at = NULL, 
                error = NULL
            WHERE project_id = ?
        """, (project_id,))
        targets_reset = cursor.rowcount
        
        # Reset services
        cursor.execute("""
            UPDATE services 
            SET status = 'pending', 
                started_at = NULL, 
                completed_at = NULL, 
                error = NULL
            WHERE target_id IN (
                SELECT target_id FROM targets WHERE project_id = ?
            )
        """, (project_id,))
        services_reset = cursor.rowcount
        
        # Reset audit tasks
        cursor.execute("""
            UPDATE audit_tasks 
            SET status = 'pending', 
                started_at = NULL, 
                completed_at = NULL, 
                duration_seconds = NULL,
                error = NULL,
                retry_count = 0
            WHERE service_id IN (
                SELECT s.service_id 
                FROM services s
                JOIN targets t ON s.target_id = t.target_id
                WHERE t.project_id = ?
            )
        """, (project_id,))
        tasks_reset = cursor.rowcount
        
        # Update project status
        cursor.execute("""
            UPDATE projects 
            SET status = 'running', 
                completed_at = NULL, 
                updated_at = ?
            WHERE project_id = ?
        """, (now, project_id))
        
        # Log to bitacora
        cursor.execute("""
            INSERT INTO bitacora_entries (
                project_id, target_id, operation, result, notes, timestamp
            ) VALUES (?, NULL, ?, ?, ?, ?)
        """, (
            project_id,
            "Project reset via script",
            "success",
            f"Reset {targets_reset} targets, {services_reset} services, {tasks_reset} tasks",
            now
        ))
        
        # Commit transaction
        conn.commit()
        
        print(f"\n✅ Reset Complete:")
        print(f"   Targets reset: {targets_reset}")
        print(f"   Services reset: {services_reset}")
        print(f"   Tasks reset: {tasks_reset}")
        print(f"\n🚀 Project is ready to run again!")
        print(f"\n   Use: audit_run(project_id=\"{project_id}\")")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python reset_project.py <project_id>")
        sys.exit(1)
    
    reset_project(sys.argv[1])
