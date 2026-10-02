#!/usr/bin/env python3
"""
Quick script to check project status
"""
import sqlite3
import sys
from pathlib import Path
import json

def check_status(project_id: str):
    """Check project status"""
    
    db_path = Path.home() / ".local" / "share" / "audit-orchestrator" / "audit_state.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get project
        cursor.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
        project = cursor.fetchone()
        
        if not project:
            print(f"❌ Project not found: {project_id}")
            sys.exit(1)
        
        # Get targets stats
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
        
        # Get next pending target
        cursor.execute("""
            SELECT ip_or_hostname, status 
            FROM targets 
            WHERE project_id = ? AND status = 'pending'
            LIMIT 1
        """, (project_id,))
        next_target = cursor.fetchone()
        
        result = {
            "project_id": project_id,
            "base_path": project["base_path"],
            "status": project["status"],
            "targets": {
                "total": targets_stats["total"],
                "pending": targets_stats["pending"],
                "running": targets_stats["running"],
                "completed": targets_stats["completed"],
                "failed": targets_stats["failed"]
            },
            "services": {
                "total": services_stats["total"],
                "pending": services_stats["pending"],
                "running": services_stats["running"],
                "completed": services_stats["completed"],
                "failed": services_stats["failed"]
            },
            "next_target": next_target["ip_or_hostname"] if next_target else None,
            "ready_to_run": targets_stats["pending"] > 0
        }
        
        print(json.dumps(result, indent=2))
        
    finally:
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python check_project_status.py <project_id>")
        sys.exit(1)
    
    check_status(sys.argv[1])
