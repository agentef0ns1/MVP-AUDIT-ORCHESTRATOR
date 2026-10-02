"""
Test Kali Server connectivity and endpoint compatibility
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_kali_server_endpoints():
    """
    Test that Kali Server has the expected endpoints.
    
    This test verifies:
    1. Server is reachable
    2. /health endpoint works
    3. /api/command endpoint exists
    """
    import requests
    
    SERVER_URL = "http://127.0.0.1:5001"
    
    print(f"🔍 Testing Kali Server at {SERVER_URL}")
    
    # Test 1: Health check
    print("\n1. Testing /health endpoint...")
    try:
        response = requests.get(f"{SERVER_URL}/health", timeout=5)
        if response.status_code == 200:
            print("   ✅ Health check successful")
        else:
            print(f"   ❌ Health check returned {response.status_code}")
            return False
    except requests.ConnectionError:
        print(f"   ❌ Cannot connect to Kali Server at {SERVER_URL}")
        print(f"   💡 Make sure Kali Server is running:")
        print(f"      kali-server-mcp --ip 0.0.0.0 --port 5001")
        return False
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return False
    
    # Test 2: Command endpoint
    print("\n2. Testing /api/command endpoint...")
    try:
        test_payload = {
            "command": "echo 'test'",
            "timeout": 5
        }
        response = requests.post(
            f"{SERVER_URL}/api/command",
            json=test_payload,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Command endpoint works")
            print(f"      Response keys: {list(result.keys())}")
            
            # Verify expected response format
            if "stdout" in result and "exit_code" in result:
                print(f"   ✅ Response format correct")
                print(f"      stdout: {result.get('stdout', '')[:50]}")
                print(f"      exit_code: {result.get('exit_code')}")
            else:
                print(f"   ⚠️  Response format unexpected")
                print(f"      Expected: stdout, exit_code")
                print(f"      Got: {result}")
        else:
            print(f"   ❌ Command endpoint returned {response.status_code}")
            print(f"      Response: {response.text[:200]}")
            return False
    
    except Exception as e:
        print(f"   ❌ Error testing command endpoint: {e}")
        return False
    
    # Test 3: Verify no /execute endpoint (old bug)
    print("\n3. Verifying /execute endpoint does NOT exist...")
    try:
        response = requests.post(
            f"{SERVER_URL}/execute",
            json={"command": "test"},
            timeout=5
        )
        if response.status_code == 404:
            print("   ✅ Correctly returns 404 for /execute (expected)")
        else:
            print(f"   ⚠️  Unexpected: /execute returned {response.status_code}")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")
    
    print("\n✅ All Kali Server connectivity tests passed!")
    return True


def test_orchestrator_kali_client():
    """Test that orchestrator kali_client uses correct endpoint"""
    print("\n🔍 Testing Orchestrator Kali Client Configuration")
    
    try:
        from audit_orchestrator.core.kali_client import KaliMCPClient
        
        # Check that client code references /api/command
        import inspect
        source = inspect.getsource(KaliMCPClient._execute_via_mcp)
        
        if "/api/command" in source:
            print("   ✅ Kali client uses correct endpoint: /api/command")
        else:
            print("   ❌ Kali client may not use correct endpoint")
            print("   💡 Check src/audit_orchestrator/core/kali_client.py")
            return False
        
        if "/execute" in source and "/api/command" not in source:
            print("   ❌ Kali client still uses old /execute endpoint!")
            print("   💡 Update kali_client.py to use /api/command")
            return False
        
        print("   ✅ Orchestrator Kali Client configuration looks good")
        return True
    
    except Exception as e:
        print(f"   ❌ Error inspecting kali_client: {e}")
        return False


def main():
    """Run all connectivity tests"""
    print("="*60)
    print("Kali Server Connectivity Tests")
    print("="*60)
    
    results = []
    
    # Test 1: Kali Server endpoints
    results.append(("Kali Server Endpoints", test_kali_server_endpoints()))
    
    # Test 2: Orchestrator client config
    results.append(("Orchestrator Client Config", test_orchestrator_kali_client()))
    
    # Summary
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
        print("\n🎉 All tests passed! Orchestrator is ready to use.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        print("📖 See TROUBLESHOOTING.md for help")
        return 1


if __name__ == "__main__":
    sys.exit(main())
