#!/usr/bin/env python3
"""
Test convenience tools that don't require project_id
"""
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_get_project_by_path():
    """Test finding project by path"""
    print("="*70)
    print("  Testing get_project_by_path()")
    print("="*70)
    print()
    
    from audit_orchestrator.config import Settings
    from audit_orchestrator.core.store import AuditStore
    
    # Use temp DB
    temp_db = Path(tempfile.gettempdir()) / "test_convenience.db"
    if temp_db.exists():
        temp_db.unlink()
    
    settings = Settings.from_args(data_dir=str(temp_db.parent))
    settings.db_path = temp_db
    store = AuditStore(settings)
    
    # Create test project
    project = store.create_project(
        base_path="/tmp/test_audit",
        input_file="open_ports.txt",
        profile="default_blackbox",
        execution_mode="type_2_post_host_llm"
    )
    
    print(f"✅ Created project: {project['project_id']}")
    print(f"   Path: {project['base_path']}")
    print(f"   Mode: {project['execution_mode']}")
    print()
    
    # Find by path
    try:
        found = store.get_project_by_path("/tmp/test_audit", "open_ports.txt")
        print(f"✅ Found project by path: {found['project_id']}")
        
        if found['project_id'] == project['project_id']:
            print(f"✅ Correct project retrieved")
        else:
            print(f"❌ Wrong project: {found['project_id']} != {project['project_id']}")
            return False
    except Exception as e:
        print(f"❌ Failed to find project: {e}")
        return False
    
    # Try non-existent path
    try:
        store.get_project_by_path("/nonexistent", "file.txt")
        print(f"❌ Should have raised error for non-existent path")
        return False
    except Exception:
        print(f"✅ Correctly raises error for non-existent path")
    
    # Cleanup
    temp_db.unlink()
    print()
    return True


def test_mcp_tools_signature():
    """Test that new MCP tools are registered"""
    print("="*70)
    print("  Testing MCP Tools Registration")
    print("="*70)
    print()
    
    try:
        from audit_orchestrator.mcp_server import (
            audit_start_and_run,
            audit_resume,
            audit_status_by_path,
        )
        
        print("✅ audit_start_and_run imported")
        print("✅ audit_resume imported")
        print("✅ audit_status_by_path imported")
        
        # Check signatures
        import inspect
        
        # audit_start_and_run
        sig = inspect.signature(audit_start_and_run)
        params = list(sig.parameters.keys())
        required = ["base_path", "input_file", "profile", "execution_mode", "reset", "max_targets"]
        for param in required:
            if param in params:
                print(f"  ✅ audit_start_and_run has '{param}' parameter")
            else:
                print(f"  ❌ audit_start_and_run missing '{param}' parameter")
                return False
        
        # audit_resume
        sig = inspect.signature(audit_resume)
        params = list(sig.parameters.keys())
        required = ["base_path", "input_file", "max_targets"]
        for param in required:
            if param in params:
                print(f"  ✅ audit_resume has '{param}' parameter")
            else:
                print(f"  ❌ audit_resume missing '{param}' parameter")
                return False
        
        # audit_status_by_path
        sig = inspect.signature(audit_status_by_path)
        params = list(sig.parameters.keys())
        required = ["base_path", "input_file"]
        for param in required:
            if param in params:
                print(f"  ✅ audit_status_by_path has '{param}' parameter")
            else:
                print(f"  ❌ audit_status_by_path missing '{param}' parameter")
                return False
        
        print()
        return True
        
    except Exception as e:
        print(f"❌ Failed to import tools: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("="*70)
    print("  Convenience Tools Test Suite")
    print("="*70)
    print()
    
    results = []
    
    # Test 1: Store method
    results.append(("get_project_by_path", test_get_project_by_path()))
    
    # Test 2: MCP tools
    results.append(("MCP tools registration", test_mcp_tools_signature()))
    
    # Summary
    print("="*70)
    print("  Test Summary")
    print("="*70)
    print()
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
