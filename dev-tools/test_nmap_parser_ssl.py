#!/usr/bin/env python3
"""
Test nmap parser with SSL service example
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.parser import parse_nmap_output


def test_ssl_service_parsing():
    """Test parsing of ssl/radan-http service"""
    print("Testing nmap parser with SSL service\n")
    print("=" * 70)
    
    # Create test nmap output (user's example)
    test_content = """Starting Nmap 7.99 ( https://nmap.org ) at 2026-09-30 10:32 -0700
Nmap scan report for 10.19.220.23
Host is up (0.053s latency).

PORT     STATE SERVICE        VERSION
8088/tcp open  ssl/radan-http myServer
"""
    
    # Write to temp file
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(test_content)
        temp_file = f.name
    
    try:
        # Parse the file
        targets_data = parse_nmap_output(temp_file)
        
        print(f"Parsed targets: {list(targets_data.keys())}\n")
        
        for target, ports in targets_data.items():
            print(f"Target: {target}")
            print(f"Ports found: {len(ports)}\n")
            
            for port_info in ports:
                print(f"  Port: {port_info['port']}")
                print(f"  Protocol: {port_info['protocol']}")
                print(f"  State: {port_info['state']}")
                print(f"  Service: '{port_info.get('service', 'N/A')}'")
                print()
                
                # Validate
                service_name = port_info.get('service', '')
                print(f"  ✓ Service name: '{service_name}'")
                
                # Check if SSL is detected
                if 'ssl' in service_name.lower() or 'tls' in service_name.lower():
                    print(f"  ✅ SSL/TLS detected in service name!")
                    print(f"  → Should use HTTPS protocol")
                else:
                    print(f"  ❌ SSL/TLS NOT detected in service name")
                    print(f"  → Would use HTTP protocol")
        
        print("\n" + "=" * 70)
        
        # Now test what profile would select
        from audit_orchestrator.core.orchestrator import AuditProfile
        import json
        
        profile_path = Path(__file__).parent.parent / "src" / "audit_orchestrator" / "audit_profiles" / "default_blackbox.json"
        profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
        profile = AuditProfile(profile_data)
        
        print("\nProfile Task Selection:")
        print("=" * 70)
        
        for target, ports in targets_data.items():
            for port_info in ports:
                service_name = port_info.get('service', 'unknown')
                tasks = profile.get_tasks_for_service(service_name)
                
                print(f"\nService: '{service_name}'")
                print(f"Tasks selected: {len(tasks)}")
                
                # Check protocols
                http_count = 0
                https_count = 0
                
                for task in tasks:
                    cmd = task.get('command', '')
                    if 'https://' in cmd:
                        https_count += 1
                    elif 'http://' in cmd:
                        http_count += 1
                
                print(f"  HTTP URLs: {http_count}")
                print(f"  HTTPS URLs: {https_count}")
                
                if https_count > 0 and http_count == 0:
                    print(f"  ✅ CORRECT: All web tasks use HTTPS")
                elif http_count > 0:
                    print(f"  ❌ PROBLEM: Some tasks use HTTP instead of HTTPS")
                    print(f"\n  Tasks with HTTP:")
                    for task in tasks:
                        cmd = task.get('command', '')
                        if 'http://' in cmd:
                            print(f"    - {task.get('type')}: {cmd}")
        
        print("\n" + "=" * 70)
        
    finally:
        # Cleanup
        Path(temp_file).unlink()


if __name__ == "__main__":
    test_ssl_service_parsing()
