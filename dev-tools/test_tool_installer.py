#!/usr/bin/env python3
"""
Test tool installer functionality
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from audit_orchestrator.core.tool_installer import (
    extract_tool_name,
    get_check_command,
    get_install_command,
    get_package_name,
    is_special_case,
)

def test_tool_extraction():
    """Test tool name extraction from commands"""
    test_cases = [
        ("nmap -sV -p 80 10.0.0.1", "nmap"),
        ("nikto -h http://example.com", "nikto"),
        ("curl -I http://example.com", "curl"),
        ("testssl.sh --fast example.com", "testssl.sh"),
        ("/usr/bin/nmap -sV 10.0.0.1", "nmap"),
        ("whatweb https://example.com:8080", "whatweb"),
        ("ffuf -u http://example.com/FUZZ -w wordlist.txt", "ffuf"),
        ("", None),
        ("   ", None),
    ]
    
    print("🧪 Testing Tool Name Extraction")
    print("=" * 80)
    
    all_passed = True
    for command, expected in test_cases:
        result = extract_tool_name(command)
        status = "✅" if result == expected else "❌"
        if result != expected:
            all_passed = False
        print(f"{status} '{command[:50]:50s}' → {result} (expected: {expected})")
    
    return all_passed


def test_package_mapping():
    """Test tool → package mapping"""
    test_cases = [
        ("nmap", "nmap"),
        ("nikto", "nikto"),
        ("testssl.sh", "testssl.sh"),
        ("wpscan", "wpscan"),
        ("enum4linux", "enum4linux"),
        ("dig", "dnsutils"),
        ("unknown-tool", "unknown-tool"),  # Should default to tool name
    ]
    
    print("\n🧪 Testing Tool → Package Mapping")
    print("=" * 80)
    
    all_passed = True
    for tool, expected_package in test_cases:
        result = get_package_name(tool)
        status = "✅" if result == expected_package else "❌"
        if result != expected_package:
            all_passed = False
        print(f"{status} {tool:20s} → {result:20s} (expected: {expected_package})")
    
    return all_passed


def test_check_commands():
    """Test check command generation"""
    test_tools = [
        "nmap",
        "nikto",
        "testssl.sh",  # Special case
        "ffuf",        # Special case
        "curl",
    ]
    
    print("\n🧪 Testing Check Commands")
    print("=" * 80)
    
    for tool in test_tools:
        check_cmd = get_check_command(tool)
        special = "⭐ (special)" if is_special_case(tool) else ""
        print(f"  {tool:15s} → {check_cmd} {special}")
    
    return True


def test_install_commands():
    """Test install command generation"""
    test_tools = [
        "nmap",
        "nikto",
        "testssl.sh",  # Special case
        "ffuf",        # Special case
        "nuclei",      # Special case
        "curl",
    ]
    
    print("\n🧪 Testing Install Commands")
    print("=" * 80)
    
    for tool in test_tools:
        install_cmd = get_install_command(tool)
        special = "⭐ (special)" if is_special_case(tool) else ""
        
        # Show first 100 chars
        cmd_preview = install_cmd[:100] + "..." if len(install_cmd) > 100 else install_cmd
        print(f"\n  Tool: {tool} {special}")
        print(f"    Command: {cmd_preview}")
    
    return True


def main():
    print("\n" + "=" * 80)
    print("  TOOL INSTALLER - Test Suite")
    print("=" * 80)
    
    results = []
    
    # Run tests
    results.append(("Tool Extraction", test_tool_extraction()))
    results.append(("Package Mapping", test_package_mapping()))
    results.append(("Check Commands", test_check_commands()))
    results.append(("Install Commands", test_install_commands()))
    
    # Summary
    print("\n" + "=" * 80)
    print("  TEST SUMMARY")
    print("=" * 80)
    
    all_passed = all(result for _, result in results)
    
    for test_name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status:10s} {test_name}")
    
    print("=" * 80)
    
    if all_passed:
        print("\n✅ All tests passed!")
        return 0
    else:
        print("\n❌ Some tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
