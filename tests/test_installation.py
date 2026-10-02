"""
Test that all modules can be imported and basic functionality works
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_imports():
    """Test that all modules can be imported"""
    print("🔍 Testing module imports...")
    
    try:
        from audit_orchestrator import __version__
        print(f"   ✅ audit_orchestrator ({__version__})")
        
        from audit_orchestrator.config import Settings
        print(f"   ✅ config.Settings")
        
        from audit_orchestrator.core.db import Database
        print(f"   ✅ core.db.Database")
        
        from audit_orchestrator.core.store import AuditStore
        print(f"   ✅ core.store.AuditStore")
        
        from audit_orchestrator.core.parser import parse_nmap_output
        print(f"   ✅ core.parser")
        
        from audit_orchestrator.core.filesystem import WorkspaceManager
        print(f"   ✅ core.filesystem.WorkspaceManager")
        
        from audit_orchestrator.core.kali_client import KaliMCPClient
        print(f"   ✅ core.kali_client.KaliMCPClient")
        
        from audit_orchestrator.core.orchestrator import AuditOrchestrator
        print(f"   ✅ core.orchestrator.AuditOrchestrator")
        
        from audit_orchestrator.mcp_server import mcp
        print(f"   ✅ mcp_server")
        
        return True
    
    except ImportError as e:
        print(f"   ❌ Import failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_settings():
    """Test Settings creation"""
    print("\n🔍 Testing Settings...")
    
    try:
        from audit_orchestrator.config import Settings
        
        settings = Settings.from_args()
        print(f"   ✅ Data dir: {settings.data_dir}")
        print(f"   ✅ DB path: {settings.db_path}")
        print(f"   ✅ Kali server URL: {settings.kali_server_url}")
        print(f"   ✅ Max time per service: {settings.max_time_per_service}s")
        
        return True
    
    except Exception as e:
        print(f"   ❌ Settings test failed: {e}")
        return False


def test_database():
    """Test Database creation"""
    print("\n🔍 Testing Database...")
    
    try:
        from audit_orchestrator.config import Settings
        from audit_orchestrator.core.db import Database
        import tempfile
        
        # Create temporary database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test.db"
            db = Database(db_path)
            
            print(f"   ✅ Database created: {db_path}")
            
            # Test connection
            with db.connection() as conn:
                cursor = conn.execute("SELECT version FROM schema_version")
                version = cursor.fetchone()["version"]
                print(f"   ✅ Schema version: {version}")
            
            return True
    
    except Exception as e:
        print(f"   ❌ Database test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_audit_profile():
    """Test loading audit profile"""
    print("\n🔍 Testing Audit Profile...")
    
    try:
        from audit_orchestrator.core.orchestrator import AuditProfile
        from pathlib import Path
        
        profile_path = Path(__file__).parent.parent / "src" / "audit_orchestrator" / "audit_profiles" / "default_blackbox.json"
        
        if not profile_path.exists():
            print(f"   ❌ Profile not found: {profile_path}")
            return False
        
        profile = AuditProfile.load_from_file(profile_path)
        print(f"   ✅ Profile loaded: {profile.profile_id}")
        print(f"   ✅ Max time per service: {profile.max_time_per_service}s")
        print(f"   ✅ Task categories: {len(profile.tasks)}")
        
        # Test getting tasks for different services
        http_tasks = profile.get_tasks_for_service("http")
        print(f"   ✅ HTTP tasks: {len(http_tasks)}")
        
        ssh_tasks = profile.get_tasks_for_service("ssh")
        print(f"   ✅ SSH tasks: {len(ssh_tasks)}")
        
        return True
    
    except Exception as e:
        print(f"   ❌ Audit profile test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("MVP Audit Orchestrator - Installation Tests")
    print("="*60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Settings", test_settings),
        ("Database", test_database),
        ("Audit Profile", test_audit_profile),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ Test '{name}' crashed: {e}")
            results.append((name, False))
    
    # Print summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\n{passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Installation is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
