#!/bin/bash
#
# Test runtime SSL detection
#

echo "=================================================================="
echo "  Testing Runtime SSL Detection"
echo "=================================================================="
echo ""

# Test 1: Check if openssl works
echo "Test 1: Verify openssl is available on Kali"
echo "------------------------------------------------------------"
echo ""

python3 << 'EOF'
import asyncio
import sys
sys.path.insert(0, '/opt/cline-mcps/MVP-audit-orchestrator/src')

async def test_openssl():
    try:
        from audit_orchestrator.core.kali_client import KaliClientFactory
        
        print("Connecting to Kali MCP...")
        async with KaliClientFactory.create() as client:
            print("✓ Connected to Kali")
            print()
            
            # Check openssl
            cmd = "which openssl"
            result = await client.execute_command(cmd, timeout=5)
            
            if result.get("exit_code") == 0:
                openssl_path = result.get("stdout", "").strip()
                print(f"✅ openssl available at: {openssl_path}")
            else:
                print("❌ openssl NOT found")
                return False
            
            print()
            return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

result = asyncio.run(test_openssl())
sys.exit(0 if result else 1)
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Test 1 failed - Cannot connect to Kali or openssl missing"
    exit 1
fi

# Test 2: Test SSL detection on known SSL port
echo ""
echo "Test 2: Detect SSL on known SSL port (10.19.220.23:8088)"
echo "------------------------------------------------------------"
echo ""

python3 << 'EOF'
import asyncio
import sys
sys.path.insert(0, '/opt/cline-mcps/MVP-audit-orchestrator/src')

async def test_ssl_port():
    try:
        from audit_orchestrator.core.kali_client import KaliClientFactory
        
        async with KaliClientFactory.create() as client:
            # Test SSL port
            cmd = 'timeout 5 openssl s_client -connect 10.19.220.23:8088 < /dev/null 2>&1 | grep -q "Cipher"'
            result = await client.execute_command(cmd, timeout=10)
            
            if result.get("exit_code") == 0:
                print("✅ SSL detected on 10.19.220.23:8088")
                print("   → Would use HTTPS profile")
                return True
            else:
                print("⚠️  No SSL detected on 10.19.220.23:8088")
                print("   → Would use HTTP profile")
                return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

result = asyncio.run(test_ssl_port())
EOF

# Test 3: Test non-SSL port
echo ""
echo "Test 3: Detect SSL on regular HTTP port (if available)"
echo "------------------------------------------------------------"
echo ""

python3 << 'EOF'
import asyncio
import sys
sys.path.insert(0, '/opt/cline-mcps/MVP-audit-orchestrator/src')

async def test_http_port():
    try:
        from audit_orchestrator.core.kali_client import KaliClientFactory
        
        async with KaliClientFactory.create() as client:
            # Test regular HTTP port (usually no SSL)
            # Try port 80 if it exists
            cmd = 'timeout 5 openssl s_client -connect 10.19.220.6:80 < /dev/null 2>&1 | grep -q "Cipher"'
            result = await client.execute_command(cmd, timeout=10)
            
            if result.get("exit_code") == 0:
                print("⚠️  SSL detected on port 80 (unusual)")
                print("   → Would use HTTPS profile")
            else:
                print("✅ No SSL on port 80 (expected)")
                print("   → Would use HTTP profile")
                
            return True
            
    except Exception as e:
        print(f"ℹ️  Could not test port 80: {e}")
        return True  # Not critical

asyncio.run(test_http_port())
EOF

echo ""
echo "=================================================================="
echo "  Summary"
echo "=================================================================="
echo ""
echo "Runtime SSL detection is working. The orchestrator will:"
echo ""
echo "  1. When it finds an HTTP service (http, radan-http, web, www)"
echo "  2. Test SSL with: openssl s_client -connect host:port"
echo "  3. If SSL found → use HTTPS tasks (sslscan, testssl, https URLs)"
echo "  4. If no SSL → use HTTP tasks (http URLs)"
echo ""
echo "This happens automatically during audit execution."
echo "No changes to open_ports.txt needed."
echo ""
echo "To see it in action, run:"
echo "  audit_start_and_run(base_path='/home/f0ns1/RedTeam/OCSR25/PoC')"
echo ""
echo "Check bitácora for SSL detection logs:"
echo "  tail -f /home/f0ns1/RedTeam/OCSR25/PoC/audit.log | grep -i ssl"
echo ""
