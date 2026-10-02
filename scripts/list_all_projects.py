#!/usr/bin/env python3
"""
List all projects in the database
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

def list_projects():
    """List all projects with statistics"""
    
    db_path = Path.home() / ".local" / "share" / "audit-orchestrator" / "audit_state.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get all projects
        cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
        projects = cursor.fetchall()
        
        if not projects:
            print(f"\nℹ️  No projects found in database")
            print(f"   Database: {db_path}")
            sys.exit(0)
        
        print(f"\n{'='*100}")
        print(f"  📊 ALL PROJECTS ({len(projects)} total)")
        print(f"{'='*100}")
        
        for i, project in enumerate(projects, 1):
            project_id = project['project_id']
            
            # Get statistics
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
            
            cursor.execute("""
                SELECT COUNT(*) as total FROM findings WHERE project_id = ?
            """, (project_id,))
            findings_count = cursor.fetchone()['total']
            
            # Check filesystem
            base_path = Path(project['base_path'])
            fs_exists = "✅" if base_path.exists() else "❌"
            
            if base_path.exists():
                target_dirs = [d for d in base_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
                size = sum(f.stat().st_size for f in base_path.rglob('*') if f.is_file())
                size_mb = size / (1024 * 1024)
                fs_info = f"{len(target_dirs)} dirs, {size_mb:.2f} MB"
            else:
                fs_info = "Not found"
            
            print(f"\n[{i}] Project: {project_id}")
            print(f"    Base Path: {project['base_path']}")
            print(f"    Input File: {project['input_file']}")
            print(f"    Status: {project['status']}")
            print(f"    Created: {project['created_at']}")
            print(f"    Targets: {targets_stats['total']} total (pending: {targets_stats['pending']}, "
                  f"completed: {targets_stats['completed']}, failed: {targets_stats['failed']})")
            print(f"    Findings: {findings_count}")
            print(f"    Filesystem: {fs_exists} {fs_info}")
        
        print(f"\n{'='*100}")
        print(f"\n💡 To delete a project:")
        print(f"   python3 scripts/delete_project_completely.py <project_id>")
        print(f"\n💡 To reset entire database:")
        print(f"   python3 scripts/reset_database_completely.py --delete-files")
        
    finally:
        conn.close()


if __name__ == "__main__":
    list_projects()
