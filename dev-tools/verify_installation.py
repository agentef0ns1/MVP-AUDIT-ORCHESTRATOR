#!/usr/bin/env python3
"""
Quick verification script for MVP Audit Orchestrator v2
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def print_status(msg, status):
    """Print status with emoji"""
    emoji = "✅" if status else "❌"
    print(f"{emoji} {msg}")


def main():
    """Verify installation"""
    print("="*70)
    print("  MVP Audit Orchestrator v2 - Installation Verification")
    print("="*70)
    print()
    
    all_ok = True
    
    # Test 1: Import core modules
    print("1. Testing imports...")
    try:
        from audit_orchestrator.config import Settings
        from audit_orchestrator.core.db import Database
        from audit_orchestrator.core.store import AuditStore
        from audit_orchestrator.core.orchestrator import AuditOrchestrator
        from audit_orchestrator.core.command_validator import validate_safe_command
        print_status("Core modules import OK", True)
    except Exception as e:
        print_status(f"Import failed: {e}", False)
        all_ok = False
    
    # Test 2: Database version
    print("\n2. Checking database...")
    try:
        from audit_orchestrator.config import Settings
        from audit_orchestrator.core.db import Database
        
        settings = Settings.from_args()
        
        if not settings.db_path.exists():
            print_status("No database yet (will be created on first use)", True)
        else:
            db = Database(settings.db_path)
            
            with db.connection() as conn:
                # Check schema version
                cursor = conn.execute("SELECT version FROM schema_version ORDER BY version DESC LIMIT 1")
                row = cursor.fetchone()
                if row and row[0] >= 2:
                    print_status(f"Database schema v{row[0]} OK", True)
                else:
                    print_status(f"Database schema old: v{row[0] if row else 0}", False)
                    all_ok = False
                
                # Check execution_mode column
                cursor = conn.execute("PRAGMA table_info(projects)")
                columns = [r[1] for r in cursor.fetchall()]
                if "execution_mode" in columns:
                    print_status("execution_mode column present", True)
                else:
                    print_status("execution_mode column missing", False)
                    all_ok = False
                
                # Check llm_execution_state table
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='llm_execution_state'"
                )
                if cursor.fetchone():
                    print_status("llm_execution_state table present", True)
                else:
                    print_status("llm_execution_state table missing", False)
                    all_ok = False
    except Exception as e:
        print_status(f"Database check failed: {e}", False)
        all_ok = False
    
    # Test 3: MCP tools
    print("\n3. Checking MCP tools...")
    try:
        from audit_orchestrator.mcp_server import (
            audit_start,
            audit_run,
            audit_llm_analyze_host,
            audit_llm_execute_poc,
            audit_llm_get_context,
            audit_llm_next_command,
        )
        print_status("All MCP tools available", True)
        
        # Check audit_start signature
        import inspect
        sig = inspect.signature(audit_start)
        if "execution_mode" in sig.parameters:
            print_status("audit_start has execution_mode parameter", True)
        else:
            print_status("audit_start missing execution_mode parameter", False)
            all_ok = False
    except Exception as e:
        print_status(f"MCP tools check failed: {e}", False)
        all_ok = False
    
    # Test 4: Command validator
    print("\n4. Testing command validator...")
    try:
        from audit_orchestrator.core.command_validator import validate_safe_command
        
        # Test safe command
        is_safe, _ = validate_safe_command("nmap -sV 10.19.220.25")
        if is_safe:
            print_status("Safe command validation OK", True)
        else:
            print_status("Safe command rejected (bug)", False)
            all_ok = False
        
        # Test unsafe command
        is_safe, _ = validate_safe_command("rm -rf /")
        if not is_safe:
            print_status("Unsafe command blocked OK", True)
        else:
            print_status("Unsafe command allowed (bug)", False)
            all_ok = False
    except Exception as e:
        print_status(f"Command validator failed: {e}", False)
        all_ok = False
    
    # Test 5: SSL detection
    print("\n5. Testing SSL service detection...")
    try:
        from audit_orchestrator.core.orchestrator import AuditProfile
        import json
        
        profile_path = Path(__file__).parent.parent / "src" / "audit_orchestrator" / "audit_profiles" / "default_blackbox.json"
        profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
        profile = AuditProfile(profile_data)
        
        # Test ssl/radan-http
        tasks = profile.get_tasks_for_service("ssl/radan-http")
        https_count = sum(1 for t in tasks if 'https://' in t.get('command', ''))
        http_count = sum(1 for t in tasks if 'http://' in t.get('command', ''))
        
        if https_count > 0 and http_count == 0:
            print_status("SSL detection working (ssl/radan-http → HTTPS)", True)
        else:
            print_status(f"SSL detection bug (HTTP:{http_count} HTTPS:{https_count})", False)
            all_ok = False
    except Exception as e:
        print_status(f"SSL detection failed: {e}", False)
        all_ok = False
    
    # Summary
    print("\n" + "="*70)
    if all_ok:
        print("  ✅ All checks passed - Installation OK")
        print("="*70)
        print("\nYou can now use the orchestrator with:")
        print("  - Type 1 (no LLM): execution_mode='type_1_no_llm'")
        print("  - Type 2 (post-host LLM): execution_mode='type_2_post_host_llm'")
        print("  - Type 3 (full LLM control): execution_mode='type_3_interactive_llm'")
        print("\nSee docs/LLM_EXECUTION_MODES.md for details.")
        return 0
    else:
        print("  ❌ Some checks failed - See errors above")
        print("="*70)
        print("\nRun migration if needed:")
        print("  python3 scripts/migrate_database.py")
        print("\nSee UPGRADE_GUIDE.md for troubleshooting.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
