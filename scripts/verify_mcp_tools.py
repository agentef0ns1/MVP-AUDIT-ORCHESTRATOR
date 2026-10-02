#!/usr/bin/env python3
"""
Verify that all MCP tools are properly registered
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def main():
    """Check MCP tools"""
    print("="*70)
    print("  MCP Tools Verification")
    print("="*70)
    print()
    
    try:
        # Import MCP server module
        from audit_orchestrator import mcp_server
        
        # Get all tool functions
        tools = [
            name for name in dir(mcp_server)
            if not name.startswith("_") and callable(getattr(mcp_server, name))
        ]
        
        # Filter only audit_ and kali_ tools
        audit_tools = sorted([t for t in tools if t.startswith("audit_") or t.startswith("kali_")])
        
        print(f"Found {len(audit_tools)} MCP tools:\n")
        
        # Convenience tools (new)
        convenience = ["audit_start_and_run", "audit_resume", "audit_status_by_path"]
        
        # Basic tools
        basic = [
            "audit_start", "audit_run", "audit_status", 
            "audit_get_findings", "audit_get_targets", "audit_get_bitacora",
            "audit_reset_project", "audit_finalize", "audit_record_finding"
        ]
        
        # LLM tools
        llm = [
            "audit_llm_analyze_host", "audit_llm_execute_poc",
            "audit_llm_get_context", "audit_llm_next_command"
        ]
        
        # Kali tools
        kali = ["kali_test_connection"]
        
        # Check convenience tools
        print("📦 Convenience Tools (new):")
        for tool in convenience:
            if tool in audit_tools:
                print(f"  ✅ {tool}")
            else:
                print(f"  ❌ {tool} - MISSING!")
        print()
        
        # Check basic tools
        print("🔧 Basic Tools:")
        for tool in basic:
            if tool in audit_tools:
                print(f"  ✅ {tool}")
            else:
                print(f"  ❌ {tool} - MISSING!")
        print()
        
        # Check LLM tools
        print("🤖 LLM Tools:")
        for tool in llm:
            if tool in audit_tools:
                print(f"  ✅ {tool}")
            else:
                print(f"  ❌ {tool} - MISSING!")
        print()
        
        # Check Kali tools
        print("🔐 Kali Tools:")
        for tool in kali:
            if tool in audit_tools:
                print(f"  ✅ {tool}")
            else:
                print(f"  ❌ {tool} - MISSING!")
        print()
        
        # Summary
        expected = set(convenience + basic + llm + kali)
        found = set(audit_tools) & expected
        
        print("="*70)
        print(f"  Summary: {len(found)}/{len(expected)} tools registered")
        print("="*70)
        
        if len(found) == len(expected):
            print("\n✅ All tools registered correctly!")
            return 0
        else:
            missing = expected - found
            print(f"\n⚠️  Missing tools: {', '.join(sorted(missing))}")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
