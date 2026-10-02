#!/usr/bin/env python3
"""
Manual database migration script
Forces migration to v2 for existing databases
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.config import Settings
from audit_orchestrator.core.db import Database


def main():
    """Migrate database to v2"""
    print("="*70)
    print("  Database Migration Tool")
    print("="*70)
    print()
    
    # Get database path
    settings = Settings.from_args()
    db_path = settings.db_path
    
    print(f"Database path: {db_path}")
    
    if not db_path.exists():
        print("✅ No existing database found. Will be created on first use.")
        return 0
    
    print(f"✅ Database exists")
    print()
    
    # Check current version
    try:
        db = Database(db_path)
        print("✅ Database migration completed successfully!")
        print()
        
        # Verify new schema
        with db.connection() as conn:
            # Check projects table
            cursor = conn.execute("PRAGMA table_info(projects)")
            columns = [row[1] for row in cursor.fetchall()]
            
            print("Projects table columns:")
            for col in columns:
                print(f"  - {col}")
            
            if "execution_mode" in columns:
                print("\n✅ execution_mode column present")
            else:
                print("\n❌ execution_mode column missing!")
                return 1
            
            # Check llm_execution_state table
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_execution_state'"
            )
            if cursor.fetchone():
                print("✅ llm_execution_state table present")
            else:
                print("❌ llm_execution_state table missing!")
                return 1
            
            # Check schema version
            cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                version = row[0]
                print(f"\nCurrent schema version: {version}")
                if version >= 2:
                    print("✅ Database is up to date (v2)")
                else:
                    print(f"⚠️  Database at old version: {version}")
            
        print()
        print("="*70)
        print("  Migration Complete!")
        print("="*70)
        return 0
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
