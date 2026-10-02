#!/bin/bash

# Verification script for v0.1.1 fix

echo "========================================"
echo "MVP Audit Orchestrator - Fix Verification"
echo "Version 0.1.1"
echo "========================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SUCCESS=0
FAILURES=0

check() {
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ PASS${NC}: $1"
        ((SUCCESS++))
    else
        echo -e "${RED}❌ FAIL${NC}: $1"
        ((FAILURES++))
    fi
}

warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
}

# Check 1: Kali Server is running
echo "1. Checking Kali Server..."
curl -s http://127.0.0.1:5001/health > /dev/null 2>&1
check "Kali Server is reachable at http://127.0.0.1:5001"

# Check 2: /api/command endpoint exists
echo ""
echo "2. Checking /api/command endpoint..."
RESPONSE=$(curl -s -X POST http://127.0.0.1:5001/api/command \
    -H "Content-Type: application/json" \
    -d '{"command":"echo test","timeout":5}')

if echo "$RESPONSE" | grep -q "stdout"; then
    check "/api/command endpoint works"
else
    check "/api/command endpoint works"
fi

# Check 3: /execute endpoint should NOT work (returns 404)
echo ""
echo "3. Verifying /execute endpoint returns 404..."
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://127.0.0.1:5001/execute \
    -H "Content-Type: application/json" \
    -d '{"command":"test"}')

if [ "$HTTP_CODE" = "404" ]; then
    check "/execute correctly returns 404 (expected)"
else
    warn "/execute returned $HTTP_CODE (expected 404)"
fi

# Check 4: Version check
echo ""
echo "4. Checking orchestrator version..."
cd "$(dirname "$0")/.."
VERSION=$(python3 -c "import sys; sys.path.insert(0, 'src'); from audit_orchestrator import __version__; print(__version__)" 2>/dev/null)

if [ "$VERSION" = "0.1.1" ]; then
    check "Orchestrator version is 0.1.1"
else
    echo -e "${RED}❌ FAIL${NC}: Version is $VERSION (expected 0.1.1)"
    ((FAILURES++))
    warn "Run: ./scripts/install.sh"
fi

# Check 5: Run connectivity tests
echo ""
echo "5. Running connectivity tests..."
python3 tests/test_kali_connection.py > /tmp/conn_test.log 2>&1

if [ $? -eq 0 ]; then
    check "Connectivity tests passed"
else
    echo -e "${RED}❌ FAIL${NC}: Connectivity tests failed"
    ((FAILURES++))
    echo "   See /tmp/conn_test.log for details"
fi

# Summary
echo ""
echo "========================================"
echo "Summary"
echo "========================================"
echo -e "Passed: ${GREEN}$SUCCESS${NC}"
echo -e "Failed: ${RED}$FAILURES${NC}"
echo ""

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}🎉 All checks passed!${NC}"
    echo ""
    echo "Your orchestrator is ready to use:"
    echo "  1. Start audit: audit_start(base_path=\"/path/to/PoC/\")"
    echo "  2. Run audit: audit_run(project_id=\"<id>\")"
    echo ""
    exit 0
else
    echo -e "${RED}⚠️  Some checks failed${NC}"
    echo ""
    echo "Troubleshooting:"
    echo "  1. Make sure Kali Server is running:"
    echo "     kali-server-mcp --ip 0.0.0.0 --port 5001"
    echo ""
    echo "  2. Reinstall orchestrator:"
    echo "     cd /opt/cline-mcps/MVP-audit-orchestrator"
    echo "     ./scripts/install.sh"
    echo ""
    echo "  3. Check TROUBLESHOOTING.md for more help"
    echo ""
    exit 1
fi
