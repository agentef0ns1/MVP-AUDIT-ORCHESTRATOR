#!/usr/bin/env python3
"""
Test SSL service detection logic
"""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.orchestrator import AuditProfile


def print_header(text: str):
    """Print formatted header"""
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70 + "\n")


def test_service_detection():
    """Test service name detection"""
    print_header("Testing SSL Service Detection")
    
    # Load profile
    profile_path = Path(__file__).parent.parent / "src" / "audit_orchestrator" / "audit_profiles" / "default_blackbox.json"
    profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
    profile = AuditProfile(profile_data)
    
    # Test cases
    test_cases = [
        ("http", "http"),
        ("https", "https"),
        ("ssl/http", "https"),
        ("ssl/radan-http", "https"),  # User's case
        ("tls/http", "https"),
        ("http-proxy", "http"),
        ("ssl/http-proxy", "https"),
        ("radan-http", "http"),  # Without ssl prefix
        ("www", "http"),
        ("web", "http"),
    ]
    
    print("Service Name Detection Test:\n")
    print(f"{'Service Name':<30} {'Expected':<15} {'Detected':<15} {'Status':<10}")
    print("-" * 70)
    
    for service_name, expected_protocol in test_cases:
        tasks = profile.get_tasks_for_service(service_name)
        
        # Determine detected protocol by checking task commands
        detected_protocol = "unknown"
        if tasks:
            # Check first task with a URL
            for task in tasks:
                cmd = task.get("command", "")
                if "https://" in cmd:
                    detected_protocol = "https"
                    break
                elif "http://" in cmd:
                    detected_protocol = "http"
                    break
        
        status = "✅ PASS" if detected_protocol == expected_protocol else "❌ FAIL"
        
        print(f"{service_name:<30} {expected_protocol:<15} {detected_protocol:<15} {status:<10}")
        
        if detected_protocol != expected_protocol:
            print(f"  → Tasks selected: {len(tasks)}")
            if tasks:
                print(f"  → First task type: {tasks[0].get('type')}")
                print(f"  → First task command: {tasks[0].get('command')}")
    
    print("\n")


def test_task_selection_details():
    """Test detailed task selection"""
    print_header("Detailed Task Selection for ssl/radan-http")
    
    # Load profile
    profile_path = Path(__file__).parent.parent / "src" / "audit_orchestrator" / "audit_profiles" / "default_blackbox.json"
    profile_data = json.loads(profile_path.read_text(encoding="utf-8"))
    profile = AuditProfile(profile_data)
    
    service_name = "ssl/radan-http"
    print(f"Testing service: {service_name}\n")
    
    # Manually trace through the logic
    service_lower = service_name.lower()
    print(f"1. service_lower = '{service_lower}'")
    print(f"2. Check exact match: '{service_lower}' in profile.tasks? {service_lower in profile.tasks}")
    print(f"3. Check 'http' in service_lower: {'http' in service_lower}")
    print(f"4. Check 'ssl' in service_lower: {'ssl' in service_lower}")
    print(f"5. Check 'tls' in service_lower: {'tls' in service_lower}")
    print(f"6. 'https' in profile.tasks? {'https' in profile.tasks}")
    print(f"7. 'http' in profile.tasks? {'http' in profile.tasks}")
    
    # Get tasks
    tasks = profile.get_tasks_for_service(service_name)
    
    print(f"\nTasks selected: {len(tasks)}")
    print("\nTask breakdown:")
    
    http_tasks = 0
    https_tasks = 0
    other_tasks = 0
    
    for i, task in enumerate(tasks, 1):
        cmd = task.get("command", "")
        task_type = task.get("type", "unknown")
        
        protocol = "other"
        if "https://" in cmd:
            protocol = "https"
            https_tasks += 1
        elif "http://" in cmd:
            protocol = "http"
            http_tasks += 1
        else:
            other_tasks += 1
        
        print(f"  {i}. [{protocol}] {task_type}: {cmd[:60]}...")
    
    print(f"\nSummary:")
    print(f"  HTTP tasks: {http_tasks}")
    print(f"  HTTPS tasks: {https_tasks}")
    print(f"  Other tasks: {other_tasks}")
    
    if https_tasks > 0 and http_tasks == 0:
        print(f"\n✅ SUCCESS: All URL tasks use HTTPS")
    elif http_tasks > 0:
        print(f"\n❌ FAILURE: Some tasks still use HTTP")
    
    print("\n")


def main():
    """Run all tests"""
    print_header("SSL/TLS Service Detection Test Suite")
    
    test_service_detection()
    test_task_selection_details()
    
    print_header("Test Suite Complete")


if __name__ == "__main__":
    main()
