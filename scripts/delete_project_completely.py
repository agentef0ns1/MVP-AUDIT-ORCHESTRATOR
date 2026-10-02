#!/usr/bin/env python3
"""
Delete a project completely: database + filesystem
"""
import sqlite3
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone

def delete_project(project_id: str, confirm: bool = False):
    """Delete project from database and filesystem"""
    
    db_path = Path.home() / ".local" / "share" / "audit-orchestrator" / "audit_state.db"
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get project info
        cursor.execute("SELECT * FROM projects WHERE project_id = ?", (project_id,))
        project = cursor.fetchone()
        
        if not project:
            print(f"❌ Project not found: {project_id}")
            sys.exit(1)
        
        base_path = Path(project['base_path'])
        
        print(f"\n{'='*80}")
        print(f"  🗑️  DELETE PROJECT COMPLETELY")
        print(f"{'='*80}")
        print(f"\n📊 Project Information:")
        print(f"   ID: {project['project_id']}")
        print(f"   Base Path: {project['base_path']}")
        print(f"   Input File: {project['input_file']}")
        print(f"   Status: {project['status']}")
        print(f"   Created: {project['created_at']}")
        
        # Get statistics
        cursor.execute("""
            SELECT COUNT(*) as total FROM targets WHERE project_id = ?
        """, (project_id,))
        targets_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM findings WHERE project_id = ?
        """, (project_id,))
        findings_count = cursor.fetchone()['total']
        
        cursor.execute("""
            SELECT COUNT(*) as total FROM bitacora_entries WHERE project_id = ?
        """, (project_id,))
        bitacora_count = cursor.fetchone()['total']
        
        print(f"\n📈 Will delete:")
        print(f"   Targets: {targets_count}")
        print(f"   Findings: {findings_count}")
        print(f"   Bitacora entries: {bitacora_count}")
        
        # Check filesystem
        target_dirs = []
        if base_path.exists():
            target_dirs = [d for d in base_path.iterdir() if d.is_dir() and not d.name.startswith('.')]
            print(f"\n📁 Filesystem:")
            print(f"   Base path exists: {base_path}")
            print(f"   Target directories: {len(target_dirs)}")
            
            if target_dirs:
                print(f"   Examples:")
                for target_dir in target_dirs[:5]:
                    size = sum(f.stat().st_size for f in target_dir.rglob('*') if f.is_file())
                    size_mb = size / (1024 * 1024)
                    print(f"     - {target_dir.name} ({size_mb:.2f} MB)")
                if len(target_dirs) > 5:
                    print(f"     ... and {len(target_dirs) - 5} more")
        else:
            print(f"\n📁 Filesystem:")
            print(f"   ⚠️  Base path does not exist: {base_path}")
        
        # Confirm deletion
        if not confirm:
            print(f"\n{'='*80}")
            print(f"⚠️  WARNING: This action is IRREVERSIBLE!")
            print(f"{'='*80}")
            print(f"\nThis will DELETE:")
            print(f"  ❌ All database records for this project")
            print(f"  ❌ All target directories and files")
            print(f"  ❌ All findings, bitacora, scan results")
            print(f"\nType 'DELETE' (in capitals) to confirm: ", end='')
            response = input()
            
            if response != 'DELETE':
                print("\n❌ Aborted. Project not deleted.")
                sys.exit(0)
        
        print(f"\n{'='*80}")
        print(f"  🗑️  DELETING PROJECT...")
        print(f"{'='*80}")
        
        # Delete from database (cascade will handle related records)
        print("\n1️⃣ Deleting from database...")
        
        cursor.execute("BEGIN TRANSACTION")
        
        # Get all targets
        cursor.execute("SELECT target_id FROM targets WHERE project_id = ?", (project_id,))
        target_ids = [row['target_id'] for row in cursor.fetchall()]
        
        deleted_counts = {}
        
        # Delete findings
        cursor.execute("DELETE FROM findings WHERE project_id = ?", (project_id,))
        deleted_counts['findings'] = cursor.rowcount
        
        # Delete bitacora entries
        cursor.execute("DELETE FROM bitacora_entries WHERE project_id = ?", (project_id,))
        deleted_counts['bitacora'] = cursor.rowcount
        
        # Delete tasks and services for each target
        services_deleted = 0
        tasks_deleted = 0
        for target_id in target_ids:
            cursor.execute("SELECT service_id FROM services WHERE target_id = ?", (target_id,))
            service_ids = [row['service_id'] for row in cursor.fetchall()]
            
            for service_id in service_ids:
                cursor.execute("DELETE FROM audit_tasks WHERE service_id = ?", (service_id,))
                tasks_deleted += cursor.rowcount
            
            cursor.execute("DELETE FROM services WHERE target_id = ?", (target_id,))
            services_deleted += cursor.rowcount
        
        deleted_counts['services'] = services_deleted
        deleted_counts['tasks'] = tasks_deleted
        
        # Delete targets
        cursor.execute("DELETE FROM targets WHERE project_id = ?", (project_id,))
        deleted_counts['targets'] = cursor.rowcount
        
        # Delete project
        cursor.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        
        conn.commit()
        
        print(f"   ✅ Deleted from database:")
        print(f"      - {deleted_counts['findings']} findings")
        print(f"      - {deleted_counts['bitacora']} bitacora entries")
        print(f"      - {deleted_counts['tasks']} audit tasks")
        print(f"      - {deleted_counts['services']} services")
        print(f"      - {deleted_counts['targets']} targets")
        print(f"      - 1 project")
        
        # Delete filesystem
        if base_path.exists():
            print(f"\n2️⃣ Deleting filesystem...")
            print(f"   Deleting: {base_path}")
            
            shutil.rmtree(base_path)
            
            print(f"   ✅ Filesystem deleted")
        else:
            print(f"\n2️⃣ Filesystem:")
            print(f"   ℹ️  Nothing to delete (base path doesn't exist)")
        
        print(f"\n{'='*80}")
        print(f"  ✅ PROJECT DELETED SUCCESSFULLY")
        print(f"{'='*80}")
        print(f"\nProject {project_id} has been completely removed.")
        print(f"Database and filesystem are clean.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Delete a project completely (database + filesystem)"
    )
    parser.add_argument(
        "project_id",
        help="Project ID to delete"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    args = parser.parse_args()
    
    delete_project(args.project_id, confirm=args.yes)
