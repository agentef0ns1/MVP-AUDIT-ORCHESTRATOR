#!/usr/bin/env python3
"""
Reset the entire audit orchestrator database and optionally all project directories
"""
import sqlite3
import shutil
import sys
from pathlib import Path

def reset_database(delete_files: bool = False, confirm: bool = False):
    """Reset entire database and optionally delete all project files"""
    
    db_path = Path.home() / ".local" / "share" / "audit-orchestrator" / "audit_state.db"
    
    if not db_path.exists():
        print(f"ℹ️  Database not found: {db_path}")
        print(f"   Nothing to reset.")
        sys.exit(0)
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get statistics BEFORE deletion
        stats = {}
        
        cursor.execute("SELECT COUNT(*) as count FROM projects")
        stats['projects'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM targets")
        stats['targets'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM services")
        stats['services'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM audit_tasks")
        stats['tasks'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM findings")
        stats['findings'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM bitacora_entries")
        stats['bitacora'] = cursor.fetchone()['count']
        
        # Get all project base paths for filesystem deletion
        cursor.execute("SELECT DISTINCT base_path FROM projects")
        base_paths = [Path(row['base_path']) for row in cursor.fetchall()]
        existing_paths = [p for p in base_paths if p.exists()]
        
        print(f"\n{'='*80}")
        print(f"  🗑️  RESET ENTIRE DATABASE")
        print(f"{'='*80}")
        print(f"\n📊 Current Database Contents:")
        print(f"   Projects: {stats['projects']}")
        print(f"   Targets: {stats['targets']}")
        print(f"   Services: {stats['services']}")
        print(f"   Audit Tasks: {stats['tasks']}")
        print(f"   Findings: {stats['findings']}")
        print(f"   Bitacora Entries: {stats['bitacora']}")
        
        if delete_files:
            print(f"\n📁 Filesystem:")
            print(f"   Project directories found: {len(existing_paths)}")
            if existing_paths:
                total_size = 0
                for base_path in existing_paths:
                    size = sum(f.stat().st_size for f in base_path.rglob('*') if f.is_file())
                    total_size += size
                    size_mb = size / (1024 * 1024)
                    print(f"     - {base_path} ({size_mb:.2f} MB)")
                
                total_mb = total_size / (1024 * 1024)
                print(f"   Total size: {total_mb:.2f} MB")
        
        if not confirm:
            print(f"\n{'='*80}")
            print(f"⚠️  WARNING: This action is IRREVERSIBLE!")
            print(f"{'='*80}")
            print(f"\nThis will:")
            print(f"  ❌ DELETE ALL records from the database")
            print(f"  ❌ RESET the database to empty state")
            
            if delete_files:
                print(f"  ❌ DELETE ALL project directories ({len(existing_paths)} directories)")
                print(f"  ❌ DELETE ALL scan results, findings, logs")
            else:
                print(f"  ℹ️  Keep project directories (use --delete-files to remove them)")
            
            print(f"\nType 'RESET' (in capitals) to confirm: ", end='')
            response = input()
            
            if response != 'RESET':
                print("\n❌ Aborted. Database not reset.")
                sys.exit(0)
        
        print(f"\n{'='*80}")
        print(f"  🗑️  RESETTING DATABASE...")
        print(f"{'='*80}")
        
        # Delete all records
        print("\n1️⃣ Deleting database records...")
        
        cursor.execute("BEGIN TRANSACTION")
        
        # Delete in correct order (respecting foreign keys)
        tables = [
            'findings',
            'audit_tasks',
            'bitacora_entries',
            'services',
            'targets',
            'projects'
        ]
        
        deleted = {}
        for table in tables:
            cursor.execute(f"DELETE FROM {table}")
            deleted[table] = cursor.rowcount
            print(f"   ✅ Deleted {deleted[table]} records from {table}")
        
        # Reset schema version to force clean state
        cursor.execute("DELETE FROM schema_version")
        cursor.execute("INSERT INTO schema_version (version, applied_at) VALUES (1, datetime('now'))")
        
        conn.commit()
        
        print(f"\n   ✅ Database reset complete")
        
        # Delete filesystem if requested
        if delete_files and existing_paths:
            print(f"\n2️⃣ Deleting project directories...")
            
            deleted_count = 0
            failed_count = 0
            
            for base_path in existing_paths:
                try:
                    print(f"   Deleting: {base_path}")
                    shutil.rmtree(base_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"   ❌ Failed to delete {base_path}: {e}")
                    failed_count += 1
            
            print(f"\n   ✅ Deleted {deleted_count} directories")
            if failed_count > 0:
                print(f"   ⚠️  Failed to delete {failed_count} directories")
        elif delete_files:
            print(f"\n2️⃣ Filesystem:")
            print(f"   ℹ️  No project directories found")
        
        print(f"\n{'='*80}")
        print(f"  ✅ RESET COMPLETE")
        print(f"{'='*80}")
        print(f"\nDatabase: {db_path}")
        print(f"Status: Empty (ready for new projects)")
        
        if delete_files:
            print(f"Filesystem: All project directories deleted")
        else:
            print(f"Filesystem: Project directories preserved (use --delete-files to remove)")
        
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
        description="Reset the entire audit orchestrator database"
    )
    parser.add_argument(
        "--delete-files",
        action="store_true",
        help="Also delete all project directories from filesystem"
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip confirmation prompt"
    )
    
    args = parser.parse_args()
    
    reset_database(delete_files=args.delete_files, confirm=args.yes)
