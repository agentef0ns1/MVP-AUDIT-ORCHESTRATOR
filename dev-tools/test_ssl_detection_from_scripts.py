#!/usr/bin/env python3
"""
Test SSL detection from nmap script output
"""
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_ssl_detection_from_scripts():
    """Test that SSL is detected from nmap script output"""
    print("="*70)
    print("  Testing SSL Detection from Nmap Scripts")
    print("="*70)
    print()
    
    from audit_orchestrator.core.parser import parse_nmap_output
    
    # Create test nmap output with SSL indicators in scripts
    nmap_output = """Starting Nmap 7.99 ( https://nmap.org ) at 2026-09-30 23:58 -0700
Nmap scan report for 10.19.220.23
Host is up (0.053s latency).

PORT     STATE SERVICE
8088/tcp open  radan-http
|_ssl-date: TLS randomness does not represent time
| ssl-cert: Subject: commonName=2102355TMS10S1100015.huawei.com/organizationName=Huawei/countryName=CN
| Not valid before: 2026-01-23T15:59:33
|_Not valid after:  2074-12-31T15:59:33
|_http-title: Did not follow redirect to https://10.19.220.23:8088/

Nmap done: 1 IP address (1 host up) scanned in 5.95 seconds
"""
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(nmap_output)
        temp_path = f.name
    
    try:
        # Parse
        targets = parse_nmap_output(temp_path)
        
        print("Parsed targets:")
        for target, ports in targets.items():
            print(f"  {target}:")
            for port in ports:
                print(f"    {port['port']}/{port['protocol']} - {port['service']}")
        print()
        
        # Verify
        if "10.19.220.23" not in targets:
            print("❌ Target not found")
            return False
        
        ports = targets["10.19.220.23"]
        if len(ports) != 1:
            print(f"❌ Expected 1 port, found {len(ports)}")
            return False
        
        port = ports[0]
        if port["port"] != 8088:
            print(f"❌ Expected port 8088, found {port['port']}")
            return False
        
        service = port["service"]
        print(f"Service detected: '{service}'")
        
        # Check if SSL was detected
        if "ssl" in service.lower() or service.lower() == "https":
            print("✅ SSL correctly detected from nmap scripts!")
            print(f"   Service marked as: {service}")
            return True
        else:
            print(f"❌ SSL not detected. Service is: {service}")
            print("   Expected: ssl/radan-http or similar")
            return False
            
    finally:
        Path(temp_path).unlink()


def test_ssl_detection_from_service_name():
    """Test that SSL is detected when already in service name"""
    print("="*70)
    print("  Testing SSL Detection from Service Name")
    print("="*70)
    print()
    
    from audit_orchestrator.core.parser import parse_nmap_output
    
    # Create test nmap output with ssl/ prefix in service
    nmap_output = """Starting Nmap 7.99 ( https://nmap.org ) at 2026-09-30 23:57 -0700
Nmap scan report for 10.19.220.23
Host is up (0.053s latency).

PORT     STATE SERVICE        VERSION
8088/tcp open  ssl/radan-http myServer

Nmap done: 1 IP address (1 host up) scanned in 5.95 seconds
"""
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(nmap_output)
        temp_path = f.name
    
    try:
        # Parse
        targets = parse_nmap_output(temp_path)
        
        print("Parsed targets:")
        for target, ports in targets.items():
            print(f"  {target}:")
            for port in ports:
                print(f"    {port['port']}/{port['protocol']} - {port['service']}")
        print()
        
        # Verify
        if "10.19.220.23" not in targets:
            print("❌ Target not found")
            return False
        
        ports = targets["10.19.220.23"]
        service = ports[0]["service"]
        
        print(f"Service detected: '{service}'")
        
        if "ssl" in service.lower():
            print("✅ SSL prefix preserved in service name!")
            return True
        else:
            print(f"❌ SSL prefix lost. Service is: {service}")
            return False
            
    finally:
        Path(temp_path).unlink()


def test_no_false_positives():
    """Test that regular HTTP is not marked as HTTPS"""
    print("="*70)
    print("  Testing No False Positives")
    print("="*70)
    print()
    
    from audit_orchestrator.core.parser import parse_nmap_output
    
    # Create test nmap output with regular HTTP (no SSL)
    nmap_output = """Nmap scan report for 10.19.220.6
Host is up (0.053s latency).

PORT   STATE SERVICE
80/tcp open  http

Nmap done: 1 IP address (1 host up) scanned in 2.00 seconds
"""
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(nmap_output)
        temp_path = f.name
    
    try:
        # Parse
        targets = parse_nmap_output(temp_path)
        
        print("Parsed targets:")
        for target, ports in targets.items():
            print(f"  {target}:")
            for port in ports:
                print(f"    {port['port']}/{port['protocol']} - {port['service']}")
        print()
        
        # Verify
        ports = targets["10.19.220.6"]
        service = ports[0]["service"]
        
        print(f"Service detected: '{service}'")
        
        if "ssl" not in service.lower() and service.lower() == "http":
            print("✅ Regular HTTP correctly identified (no false SSL detection)")
            return True
        else:
            print(f"❌ False positive! Service marked as: {service}")
            return False
            
    finally:
        Path(temp_path).unlink()


def main():
    """Run all tests"""
    print("="*70)
    print("  SSL Detection from Nmap Scripts - Test Suite")
    print("="*70)
    print()
    
    results = []
    
    # Test 1: SSL detection from scripts
    results.append(("SSL from scripts", test_ssl_detection_from_scripts()))
    print()
    
    # Test 2: SSL from service name
    results.append(("SSL from service name", test_ssl_detection_from_service_name()))
    print()
    
    # Test 3: No false positives
    results.append(("No false positives", test_no_false_positives()))
    print()
    
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
