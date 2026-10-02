#!/bin/bash
#
# Demo: Convenience Tools Usage
# Shows the difference between old and new workflows
#

set -e

DEMO_DIR="/tmp/audit_convenience_demo_$$"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=================================================================="
echo "  Convenience Tools Demo"
echo "=================================================================="
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "Cleaning up demo directory: $DEMO_DIR"
    rm -rf "$DEMO_DIR"
}
trap cleanup EXIT

# Create demo directory
mkdir -p "$DEMO_DIR"
cd "$DEMO_DIR"

# Create sample nmap output
cat > open_ports.txt << 'EOF'
Nmap scan report for 192.168.1.100
Host is up (0.001s latency).
PORT     STATE SERVICE    VERSION
22/tcp   open  ssh        OpenSSH 8.2
80/tcp   open  http       nginx 1.18.0
443/tcp  open  ssl/http   nginx 1.18.0

Nmap scan report for 192.168.1.101
Host is up (0.002s latency).
PORT     STATE SERVICE    VERSION
3306/tcp open  mysql      MySQL 8.0.25
EOF

echo "Created demo workspace: $DEMO_DIR"
echo "Created sample nmap output:"
cat open_ports.txt
echo ""

echo "=================================================================="
echo "  Method 1: Traditional Workflow (manual project_id handling)"
echo "=================================================================="
echo ""
echo "Steps:"
echo "  1. audit_start()          → Get project_id"
echo "  2. Copy project_id from JSON"
echo "  3. audit_run(project_id)  → Run audit"
echo "  4. audit_status(project_id) → Check status"
echo ""
echo "Problems:"
echo "  ❌ Multiple steps"
echo "  ❌ Manual UUID extraction"
echo "  ❌ Copy/paste errors"
echo "  ❌ High token usage"
echo ""

echo "=================================================================="
echo "  Method 2: Convenience Tools (automatic project_id handling)"
echo "=================================================================="
echo ""
echo "Steps:"
echo "  1. audit_start_and_run(base_path) → Start + Run in one"
echo "  2. audit_status_by_path(base_path) → Check status"
echo ""
echo "Benefits:"
echo "  ✅ Single command"
echo "  ✅ No UUID handling"
echo "  ✅ Fewer errors"
echo "  ✅ Lower tokens"
echo ""

echo "=================================================================="
echo "  Usage Example (conceptual - requires MCP server running)"
echo "=================================================================="
echo ""

cat << 'EXAMPLE'
# From Cursor chat or Python:

# OLD WAY:
result = audit_start(base_path="/tmp/audit", input_file="open_ports.txt")
project_id = result["project_id"]  # ← Manual extraction
audit_run(project_id=project_id)
audit_status(project_id=project_id)

# NEW WAY:
audit_start_and_run(base_path="/tmp/audit", input_file="open_ports.txt")
audit_status_by_path(base_path="/tmp/audit")

# RESUME (if interrupted):
audit_resume(base_path="/tmp/audit")
EXAMPLE

echo ""
echo "=================================================================="
echo "  Real Execution (if MCP server is running)"
echo "=================================================================="
echo ""

# Check if MCP server is reachable
if command -v python3 &> /dev/null; then
    echo "Testing tool availability..."
    
    python3 << 'PYCODE'
import sys
sys.path.insert(0, "/opt/cline-mcps/MVP-audit-orchestrator/src")

try:
    from audit_orchestrator.mcp_server import (
        audit_start_and_run,
        audit_resume,
        audit_status_by_path
    )
    print("✅ All convenience tools available")
    print("")
    print("Tools:")
    print("  - audit_start_and_run")
    print("  - audit_resume")
    print("  - audit_status_by_path")
except Exception as e:
    print(f"❌ Error importing tools: {e}")
    sys.exit(1)
PYCODE

else
    echo "⚠️  Python3 not found, skipping tool check"
fi

echo ""
echo "=================================================================="
echo "  Demo Complete"
echo "=================================================================="
echo ""
echo "For more information:"
echo "  - README.md"
echo "  - docs/USO_RAPIDO.md"
echo "  - examples/convenience_workflow.md"
echo "  - FEATURE_CONVENIENCE_TOOLS.md"
echo ""
echo "Demo workspace will be cleaned up on exit."
