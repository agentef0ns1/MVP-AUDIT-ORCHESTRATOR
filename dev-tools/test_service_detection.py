#!/usr/bin/env python3
"""
Test service type detection for SSL/TLS
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.orchestrator import AuditProfile

def test_service_detection():
    """Test service detection logic"""
    
    # Load profile
    profile_path = Path(__file__).parent.parent / "src" / "audit_orchestrator" / "audit_profiles" / "default_blackbox.json"
    profile = AuditProfile.load_from_file(profile_path)
    
    # Test cases
    test_cases = [
        ("http", "http"),           # Plain HTTP
        ("https", "https"),         # Plain HTTPS
        ("ssl/http", "https"),      # SSL wrapped HTTP
        ("ssl/radan-http", "https"),# SSL wrapped custom HTTP (tu caso)
        ("tls/http", "https"),      # TLS wrapped HTTP
        ("http-proxy", "http"),     # HTTP proxy
        ("ssh", "ssh"),             # SSH
        ("ftp", "ftp"),             # FTP
        ("unknown", "default"),     # Unknown service
        ("myServer", "default"),    # Custom service name
    ]
    
    print("🧪 Testing Service Detection Logic")
    print("=" * 70)
    
    all_passed = True
    
    for service_name, expected_profile in test_cases:
        tasks = profile.get_tasks_for_service(service_name)
        
        # Determine which profile was used based on tasks
        detected_profile = "unknown"
        if tasks:
            # Check first task command to determine profile
            first_cmd = tasks[0].get("command", "") if len(tasks) > 0 else ""
            
            # Check all task commands to determine profile
            all_cmds = " ".join([t.get("command", "") for t in tasks])
            
            if "sslscan" in all_cmds or "testssl" in all_cmds or "https://" in all_cmds:
                detected_profile = "https"
            elif "http://" in all_cmds or "whatweb http://" in all_cmds:
                detected_profile = "http"
            elif "ssh-audit" in all_cmds:
                detected_profile = "ssh"
            elif "ftp-anon" in all_cmds:
                detected_profile = "ftp"
            elif "nmap --script vuln" in all_cmds:
                detected_profile = "default"
            else:
                detected_profile = "unknown"
        else:
            detected_profile = "none"
        
        passed = detected_profile == expected_profile
        status = "✅" if passed else "❌"
        
        if not passed:
            all_passed = False
        
        print(f"{status} {service_name:20s} → {detected_profile:10s} (expected: {expected_profile})")
        
        # Show first non-all_services task for debugging
        if not passed and tasks:
            for task in tasks:
                cmd = task.get("command", "")
                if "nmap -sV" not in cmd and "nmap -sC" not in cmd:
                    print(f"   First task: {cmd}")
                    break
    
    print("=" * 70)
    if all_passed:
        print("✅ All tests passed!")
        return 0
    else:
        print("❌ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(test_service_detection())
