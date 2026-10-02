#!/usr/bin/env python3
"""
Test nmap parser with multiple formats and SSL variations
"""
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.parser import parse_nmap_output
from audit_orchestrator.core.orchestrator import AuditProfile
import json


def test_format(name, content, expected_services):
    """Test a specific nmap format"""
    print(f"\n{'='*70}")
    print(f"Testing: {name}")
    print(f"{'='*70}\n")
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(content)
        temp_file = f.name
    
    try:
        # Parse
        targets_data = parse_nmap_output(temp_file)
        
        if not targets_data:
            print("❌ FAIL: No targets parsed")
            return False
        
        # Load profile
        profile_path = Path(__file__).parent.parent / "src" / "audit_orchestrator" / "audit_profiles" / "default_blackbox.json"
        profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
        profile = AuditProfile(profile_data)
        
        all_ok = True
        
        for target, ports in targets_data.items():
            print(f"Target: {target}")
            print(f"Ports: {len(ports)}\n")
            
            for port_info in ports:
                service_name = port_info.get('service', 'unknown')
                port = port_info['port']
                
                # Check expected service
                expected = expected_services.get(port)
                if expected is None:
                    print(f"  ⚠️  Port {port}: No expectation defined")
                    continue
                
                print(f"  Port {port}:")
                print(f"    Service: '{service_name}'")
                print(f"    Expected protocol: {expected}")
                
                # Get tasks
                tasks = profile.get_tasks_for_service(service_name)
                
                # Check protocols
                http_count = sum(1 for t in tasks if 'http://' in t.get('command', ''))
                https_count = sum(1 for t in tasks if 'https://' in t.get('command', ''))
                
                # Validate
                if expected == "https":
                    if https_count > 0 and http_count == 0:
                        print(f"    ✅ PASS: Using HTTPS ({https_count} tasks)")
                    else:
                        print(f"    ❌ FAIL: Expected HTTPS, got HTTP:{http_count} HTTPS:{https_count}")
                        all_ok = False
                elif expected == "http":
                    if http_count > 0 and https_count == 0:
                        print(f"    ✅ PASS: Using HTTP ({http_count} tasks)")
                    else:
                        print(f"    ❌ FAIL: Expected HTTP, got HTTP:{http_count} HTTPS:{https_count}")
                        all_ok = False
                else:  # other/none
                    print(f"    ℹ️  Non-web service (HTTP:{http_count} HTTPS:{https_count})")
                
                print()
        
        return all_ok
        
    finally:
        Path(temp_file).unlink()


def main():
    """Run all format tests"""
    print("="*70)
    print("  Nmap Parser - SSL/HTTPS Detection Test Suite")
    print("="*70)
    
    tests = []
    
    # Test 1: User's original example
    tests.append(("User's SSL/Radan-HTTP Example", """
Starting Nmap 7.99 ( https://nmap.org ) at 2026-09-30 10:32 -0700
Nmap scan report for 10.19.220.23
Host is up (0.053s latency).

PORT     STATE SERVICE        VERSION
8088/tcp open  ssl/radan-http myServer
""", {8088: "https"}))
    
    # Test 2: Multiple SSL services
    tests.append(("Multiple SSL Services", """
Nmap scan report for 192.168.1.100
Host is up.

PORT     STATE SERVICE     VERSION
80/tcp   open  http        nginx 1.18.0
443/tcp  open  ssl/http    nginx 1.18.0
8080/tcp open  http-proxy  
8443/tcp open  ssl/http-alt Apache httpd
""", {80: "http", 443: "https", 8080: "http", 8443: "https"}))
    
    # Test 3: TLS variants
    tests.append(("TLS Variants", """
Nmap scan report for test.example.com
Host is up.

PORT     STATE SERVICE   VERSION
443/tcp  open  tls/http  Apache
8443/tcp open  ssl/https nginx
9443/tcp open  https     lighttpd
""", {443: "https", 8443: "https", 9443: "https"}))
    
    # Test 4: Mixed services
    tests.append(("Mixed Web and Non-Web", """
Nmap scan report for 10.10.10.10

PORT     STATE SERVICE     VERSION
22/tcp   open  ssh         OpenSSH 8.2
80/tcp   open  http        Apache
443/tcp  open  ssl/http    Apache
3306/tcp open  mysql       MySQL 5.7
8088/tcp open  ssl/radan-http myServer
""", {22: "other", 80: "http", 443: "https", 3306: "other", 8088: "https"}))
    
    # Test 5: Legacy format (IP only)
    tests.append(("Legacy Format (IP only)", """
10.19.220.25
Discovered open port 443/tcp on 10.19.220.25
443/tcp open ssl/http nginx
""", {443: "https"}))
    
    # Run all tests
    results = []
    for name, content, expected in tests:
        result = test_format(name, content, expected)
        results.append((name, result))
    
    # Summary
    print("\n" + "="*70)
    print("  Test Summary")
    print("="*70 + "\n")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! SSL/HTTPS detection working correctly.")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
