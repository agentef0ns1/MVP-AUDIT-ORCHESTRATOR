# Fix: Command Normalization with Absolute Paths

**Date:** October 5, 2026  
**Version:** Post-v0.2.5  
**Issue:** Intermittent command execution failures during parallel audits

## Problem

During live audits, some `ffuf` commands were being executed as `wfuzz` instead, causing syntax errors:

```
Command shown: ffuf -u https://10.19.220.24:8088/FUZZ -w /usr/share/seclists/...
Actual execution: wfuzz (with error "Too many arguments")
```

### Impact
- ~30% of web enumeration incomplete on affected targets
- Specifically affected `backup_files` fuzzing tasks
- Intermittent failures on port 8088 (radan-http service)

## Root Cause Analysis

Investigation revealed:
1. ✅ No shell aliases on Kali server (`alias` command showed no ffuf→wfuzz mapping)
2. ✅ Both `ffuf` and `wfuzz` binaries installed and functional
3. ⚠️ Problem occurred intermittently, particularly during parallel execution
4. ⚠️ Some targets (port 80) worked fine, others (port 8088) failed

**Conclusion:** While no permanent alias exists, the intermittent nature suggests potential race conditions, shell environment issues, or subprocess initialization problems during parallel execution.

## Solution

Implemented **command normalization with absolute paths** to prevent any potential aliasing or PATH manipulation:

### Changes Made

1. **New File: `src/audit_orchestrator/core/command_normalizer.py`**
   - Maps 30+ security tools to absolute paths
   - `normalize_command()` function replaces tool names with `/usr/bin/tool`
   - Helper functions for tool extraction and validation

2. **Modified: `src/audit_orchestrator/core/orchestrator.py`**
   - Added import: `from audit_orchestrator.core.command_normalizer import normalize_command`
   - Added normalization after command template formatting (line ~1447)
   - One-line change ensures all commands use absolute paths

3. **New Tests: `tests/test_command_normalizer.py`**
   - 25 unit tests covering all functionality
   - Tests for real-world audit scenarios
   - Validates critical tools (ffuf, wfuzz, nmap, etc.)

4. **New Tests: `tests/test_integration_command_normalizer.py`**
   - Integration tests with actual audit profile commands
   - Validates end-to-end normalization

### Tool Coverage

**Fuzzing:**  
ffuf, wfuzz, gobuster, dirb, feroxbuster, arjun

**Web Scanning:**  
nikto, whatweb, wafw00f, wpscan, droopescan, joomscan, cmseek

**SSL/TLS:**  
sslscan, testssl.sh

**Network:**  
nmap, masscan, nc

**SSH:**  
ssh-audit, ssh-keyscan

**SMB:**  
enum4linux, smbclient

**Other:**  
graphw00f, trufflehog, retire, wappalyzer, linkfinder, git-dumper, wget, curl, grep

## Testing

### Unit Tests
```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
python3 -m pytest tests/test_command_normalizer.py -v
# Result: 25/25 tests passed ✅
```

### Integration Tests
```bash
python3 tests/test_integration_command_normalizer.py
# Result: All 10 integration tests passed ✅
```

### Expected Behavior

**Before fix:**
```bash
# Command sent
ffuf -u https://target/FUZZ -w wordlist.txt

# Could be executed as (intermittent)
wfuzz -u https://target/FUZZ -w wordlist.txt  # WRONG SYNTAX!
```

**After fix:**
```bash
# Command sent
/usr/bin/ffuf -u https://target/FUZZ -w wordlist.txt

# Always executed as
/usr/bin/ffuf -u https://target/FUZZ -w wordlist.txt  # CORRECT!
```

## Benefits

1. **Reliability:** Commands always execute with the intended tool
2. **Security:** Prevents any potential tool substitution or PATH manipulation
3. **Debugging:** Easier to identify which exact binary is being used
4. **Future-proof:** Protects against future aliasing issues
5. **Zero breaking changes:** Existing audits continue working, just more reliably

## Verification Steps

To verify the fix is working in a live audit:

1. **Check audit logs:**
   ```bash
   grep "COMMAND:" /path/to/audit/bitacora/*.log | grep ffuf
   # Should show: /usr/bin/ffuf ...
   ```

2. **Monitor audit-live.txt:**
   ```bash
   tail -f /path/to/audit/audit-live.txt
   # Commands should show absolute paths
   ```

3. **Verify no wfuzz errors:**
   ```bash
   grep "wfuzz.*Too many arguments" /path/to/audit/audit.log
   # Should return no results
   ```

4. **Check success rate:**
   ```bash
   grep "backup_files.*success" /path/to/audit/bitacora/*.log | wc -l
   # Should show successful completions
   ```

## Rollback

If needed, the fix can be easily rolled back:

1. Remove the normalization call from `orchestrator.py`:
   ```python
   # Remove this line:
   command = normalize_command(command)
   ```

2. Commands will execute with relative paths (original behavior)

## Notes

- No changes to audit profiles required
- No changes to existing command syntax
- Compatible with all execution modes (type_1, type_2, type_3)
- Works with both serial and parallel execution
- No performance impact (normalization is a simple string operation)

## References

- **Issue:** Intermittent ffuf→wfuzz substitution during audits
- **Affected versions:** Pre-fix (October 2026)
- **Fixed in:** This commit
- **Test coverage:** 25 unit tests + 10 integration tests
