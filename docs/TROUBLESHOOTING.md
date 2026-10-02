# Troubleshooting Guide - MVP Audit Orchestrator

## Issue: Repeated POST /execute Requests with 404 Errors

### Problem Description

The orchestrator was making repeated requests to `/execute` endpoint which doesn't exist in the Kali Server, causing 404 errors and infinite retry loops.

### Root Cause

The `kali_client.py` was using the wrong endpoint. The actual Kali Server uses `/api/command` not `/execute`.

### Solution Applied

✅ **Fixed in latest version:**

1. Updated `kali_client.py` to use correct endpoint: `/api/command`
2. Changed error handling to return error results instead of raising exceptions (prevents retry loops)
3. Added comprehensive try-catch blocks to prevent any unhandled exceptions
4. Made `execute_command` method never raise exceptions

### Kali Server Endpoints Reference

The MCP Kali Server (`http://127.0.0.1:5001`) provides these endpoints:

- `POST /api/command` - Execute generic command (⭐ used by orchestrator)
- `POST /api/tools/nmap` - Execute nmap specifically  
- `POST /api/tools/nikto` - Execute nikto
- `POST /api/tools/gobuster` - Execute gobuster
- `POST /api/tools/dirb` - Execute dirb
- `GET /health` - Health check
- `GET /mcp/capabilities` - Get MCP capabilities

### Expected Payload Format

```json
{
  "command": "nmap -sV 10.19.220.23",
  "timeout": 900,
  "cwd": "/path/to/working/dir"  // optional
}
```

### Expected Response Format

```json
{
  "stdout": "..command output..",
  "stderr": "..error output..",
  "exit_code": 0,
  "timed_out": false,
  "error": null
}
```

## Verifying the Fix

### 1. Check Kali Server is Running

```bash
curl http://127.0.0.1:5001/health
```

Expected: `200 OK` response

### 2. Test Command Execution

```bash
curl -X POST http://127.0.0.1:5001/api/command \
  -H "Content-Type: application/json" \
  -d '{"command": "echo test", "timeout": 10}'
```

Expected: JSON response with `stdout: "test"`

### 3. Reinstall Orchestrator

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
./scripts/install.sh
```

### 4. Test Audit Start (without running full audit)

```python
# From LLM/MCP client:
audit_start(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC/",
    input_file="open_ports.txt"
)
```

This should complete without errors and return a `project_id`.

### 5. Test Single Target Audit

```python
# Test with max_targets=1 to audit only first target
audit_run(project_id="<your-project-id>", max_targets=1)
```

Monitor the Kali server logs. You should see:
- Requests to `/api/command` (not `/execute`)
- Successful 200 responses
- No infinite loops

## If Problems Persist

### Check 1: Verify Kali Server Version

```bash
cd /opt/cline-mcps/MCP-Kali-Server
grep "app.route" server.py | head -5
```

Should show routes like `/api/command`, `/api/tools/nmap`, etc.

If not, your Kali Server may be outdated. Update it or ensure you're running the correct version.

### Check 2: Network Connectivity

```bash
# From the machine running orchestrator:
telnet 127.0.0.1 5001
```

Should connect successfully. If not, check firewall or if Kali Server is running on a different IP.

### Check 3: Check Orchestrator Logs

```bash
# View SQLite database to see task statuses
sqlite3 ~/.local/share/audit-orchestrator/audit_state.db

# Check recent tasks
SELECT task_type, status, error FROM audit_tasks ORDER BY started_at DESC LIMIT 10;

# Check recent bitacora entries
SELECT timestamp, operation, result FROM bitacora_entries ORDER BY timestamp DESC LIMIT 20;
```

### Check 4: Verbose Logging

Add logging to see what's happening:

```bash
# Run orchestrator with debug logging
cd /opt/cline-mcps/MVP-audit-orchestrator
python3 -c "
import logging
logging.basicConfig(level=logging.DEBUG)
# Your test code here
"
```

## Known Limitations

1. **Sequential Execution**: Processes one target at a time (not parallel)
2. **Command Failures**: If Kali Server is unreachable, commands will fail but audit continues
3. **Network Delays**: Initial connection to Kali Server may be slow on first request

## Emergency: Dry-Run Mode

If you want to test the orchestrator WITHOUT executing real commands:

### Option 1: Mock the Kali Client

Edit `kali_client.py` temporarily:

```python
async def execute_command(self, command, timeout=None, ...):
    # Mock response - don't execute
    return {
        "success": True,
        "output": f"MOCK: Would execute: {command}",
        "stderr": "",
        "exit_code": 0,
        "duration": 0.1,
        "timed_out": False,
        "error": None
    }
```

### Option 2: Use Limited Scope

Start audit with `max_targets=1` to test with minimal impact:

```python
audit_run(project_id="...", max_targets=1)
```

## Getting Help

1. **Check logs**: `~/.local/share/audit-orchestrator/audit_state.db`
2. **Check bitacora**: `<base_path>/<target>/bitacora/audit_*.log`
3. **Check Kali Server logs**: Where you ran `kali-server-mcp`
4. **Review this guide**: `TROUBLESHOOTING.md`
5. **Check main docs**: `README.md`, `QUICK_START.md`

## After Fixing

Once the issue is resolved:

1. ✅ Kali Server should show successful POST requests to `/api/command`
2. ✅ No more 404 errors
3. ✅ No infinite retry loops
4. ✅ Tasks complete successfully or fail gracefully
5. ✅ Audit progresses through targets sequentially

---

**Status**: ✅ Issue fixed in current version  
**Date**: 2026-09-30  
**Version**: 0.1.0+fix1
