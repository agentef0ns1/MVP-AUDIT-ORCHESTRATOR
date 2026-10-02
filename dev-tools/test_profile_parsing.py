#!/usr/bin/env python3
"""
Test script to verify audit profile parsing and validation
"""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.command_validator import validate_safe_command, ALLOWED_TOOLS


def test_profile_parsing(profile_path: Path) -> tuple[bool, str]:
    """Test if profile can be parsed and has valid structure"""
    try:
        with open(profile_path, 'r') as f:
            profile = json.load(f)
        
        # Check required fields
        required_fields = ['profile_id', 'description']
        for field in required_fields:
            if field not in profile:
                return False, f"Missing required field: {field}"
        
        # If has extends, it's a variant profile (minimal structure)
        if 'extends' in profile:
            print(f"  ✓ Profile extends '{profile['extends']}' (variant profile)")
            return True, "Valid variant profile"
        
        # Check tasks structure for full profiles
        if 'tasks' not in profile:
            return False, "Missing 'tasks' section"
        
        tasks = profile['tasks']
        total_tasks = 0
        services = []
        
        for service, task_list in tasks.items():
            services.append(service)
            if not isinstance(task_list, list):
                return False, f"Tasks for service '{service}' must be a list"
            
            for idx, task in enumerate(task_list):
                if 'type' not in task or 'command' not in task or 'description' not in task:
                    return False, f"Task {idx} in service '{service}' missing required fields"
                
                # Validate command safety
                is_safe, reason = validate_safe_command(task['command'])
                if not is_safe:
                    return False, f"Unsafe command in {service}:{task['type']}: {reason}"
                
                total_tasks += 1
        
        print(f"  ✓ {len(services)} services defined: {', '.join(services)}")
        print(f"  ✓ {total_tasks} total tasks")
        print(f"  ✓ All commands validated as safe")
        
        # Check finding_rules if present
        if 'finding_rules' in profile:
            rules = profile['finding_rules'].get('auto_detect', {})
            print(f"  ✓ {len(rules)} finding rules defined")
        
        return True, f"Valid profile with {total_tasks} tasks"
        
    except json.JSONDecodeError as e:
        return False, f"JSON parsing error: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Test all audit profiles"""
    profiles_dir = Path(__file__).parent.parent / "src" / "audit_orchestrator" / "audit_profiles"
    
    print("=" * 70)
    print("Testing Audit Profile Parsing and Validation")
    print("=" * 70)
    
    # List all profile files
    profile_files = sorted(profiles_dir.glob("*.json"))
    
    if not profile_files:
        print("❌ No profile files found!")
        return 1
    
    print(f"\nFound {len(profile_files)} profile(s) to test:\n")
    
    all_passed = True
    results = []
    
    for profile_file in profile_files:
        print(f"Testing: {profile_file.name}")
        is_valid, message = test_profile_parsing(profile_file)
        
        if is_valid:
            print(f"  ✅ PASSED: {message}\n")
            results.append((profile_file.name, "PASS", message))
        else:
            print(f"  ❌ FAILED: {message}\n")
            results.append((profile_file.name, "FAIL", message))
            all_passed = False
    
    # Print summary
    print("=" * 70)
    print("Summary:")
    print("=" * 70)
    for name, status, msg in results:
        status_icon = "✅" if status == "PASS" else "❌"
        print(f"{status_icon} {name}: {status}")
    
    # Print allowed tools info
    print("\n" + "=" * 70)
    print(f"Command Validator: {len(ALLOWED_TOOLS)} allowed reconnaissance tools")
    print("=" * 70)
    print("Sample tools:", ", ".join(ALLOWED_TOOLS[:10]), "...")
    
    if all_passed:
        print("\n✅ All profiles validated successfully!")
        return 0
    else:
        print("\n❌ Some profiles failed validation")
        return 1


if __name__ == "__main__":
    sys.exit(main())
