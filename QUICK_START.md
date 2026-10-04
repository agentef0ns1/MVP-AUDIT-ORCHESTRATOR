# Quick Start Guide - MVP Audit Orchestrator

## 1. Installation (5 minutes)

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
chmod +x scripts/install.sh
./scripts/install.sh
```

## 2. Configure Kali Server URL (Optional)

**Default**: `http://127.0.0.1:5001`

If your Kali MCP server uses a different port or host:

```bash
export KALI_SERVER_URL="http://127.0.0.1:8080"
```

Or set permanently in `~/.bashrc`:
```bash
echo 'export KALI_SERVER_URL="http://kali-server:5001"' >> ~/.bashrc
source ~/.bashrc
```

📖 **Full config guide**: [CONFIGURAR_PUERTO_KALI.md](CONFIGURAR_PUERTO_KALI.md)

## 3. Configure MCP Client

**For Cline:**
Edit `~/.config/Code/User/globalStorage/saoudrizwan.claude-dev/settings/cline_mcp_settings.json`

**For Cursor:**
Edit `~/.cursor-tutor/mcp.json`

Add:
```json
{
  "mcpServers": {
    "audit-orchestrator": {
      "command": "/opt/cline-mcps/MVP-audit-orchestrator/.venv/bin/python",
      "args": [
        "-m", "audit_orchestrator.mcp_server",
        "--kali-server-url", "http://127.0.0.1:5001",
        "--data-dir", "/home/f0ns1/.local/share/audit-orchestrator"
      ],
      "env": {
        "AUDIT_MAX_CONCURRENT": "10"
      },
      "timeout": 3600
    }
  }
}
```

## 4. Verify MCP Kali is Running

```bash
# Quick health check
curl http://127.0.0.1:5001/health

# Or run comprehensive verification (v0.1.1+)
cd /opt/cline-mcps/MVP-audit-orchestrator
./scripts/verify-fix.sh
```

**Expected:** All checks should pass ✅

If not running, start your MCP Kali server:
```bash
kali-server-mcp --ip 0.0.0.0 --port 5001
```

## 5. Prepare nmap input

Any of these files can be the audit input. The parser picks the format automatically.

```bash
nmap -sV -p- --min-rate 5000 -v 10.19.220.0/24 -oN open_ports.txt

# or several hosts concatenated
for i in $(cat hosts.txt); do
  echo "$i"
  nmap -p- --min-rate 5000 -v "$i" | grep open
done > open_ports.txt
```

See [docs/FORMATOS_NMAP.md](docs/FORMATOS_NMAP.md).

## 6. Run Your First Audit

### Option A: Simple Prompt

Send to your LLM:
```
Usa audit-orchestrator:
1. audit_start con base_path="/home/f0ns1/RedTeam/OCSR25/PoC/" y input_file="open_ports.txt"
2. audit_run con el project_id devuelto
3. Continúa hasta que done sea true
4. audit_finalize para generar resumen
```

### Option B: Step by Step

```
1. audit_start(
     base_path="/home/f0ns1/RedTeam/OCSR25/PoC/",
     input_file="open_ports.txt",
     profile="default_blackbox"
   )
```

Note the `project_id` from response.

```
2. audit_run(project_id="<your-project-id>")
```

Wait for completion (`done: true`).

```
3. audit_finalize(project_id="<your-project-id>")
```

## 7. Check Results

```bash
cd /home/f0ns1/RedTeam/OCSR25/PoC/

# View executive summary
cat RESUMEN-AUDITORIA.md

# Browse target directories
ls -la 10.19.220.*/

# View findings for a target
cat 10.19.220.23/findings/INDICE.md

# View audit log
cat 10.19.220.23/bitacora/audit_*.log
```

## 8. Monitor Progress (Optional)

While audit is running:
```
audit_status(project_id="<your-project-id>")
```

Returns:
- Current target being audited
- Services completed
- Findings count
- Last operation

## Input File Format

The parser accepts nmap normal (`-oN`), grepable (`-oG`), XML (`-oX`), and several scans concatenated from a `for` loop. Details: [docs/FORMATOS_NMAP.md](docs/FORMATOS_NMAP.md).

A legacy plaintext file still works:

```
10.19.220.23
Discovered open port 22/tcp on 10.19.220.23
Discovered open port 8088/tcp on 10.19.220.23
22/tcp   open  ssh
8088/tcp open  radan-http

10.19.220.24
Discovered open port 80/tcp on 10.19.220.24
80/tcp   open  http
```

## Common Commands

### List all projects
```
audit_list_projects()
```

### Get findings for a project
```
audit_get_findings(project_id="<id>", severity="high")
```

### View audit log
```
audit_get_bitacora(project_id="<id>", target="10.19.220.23")
```

### Test Kali connection
```
kali_test_connection()
```

## Expected Timeline

For your current scan (52 targets, 948 ports):
- **Setup:** 5 minutes
- **Per target:** ~5-20 minutes (depends on services)
- **Total estimate:** 4-17 hours (if no issues)

The orchestrator will continue automatically even if you disconnect!

## Output Structure

```
/home/f0ns1/RedTeam/OCSR25/PoC/
├── open_ports.txt              # Your input
├── RESUMEN-AUDITORIA.md        # Executive summary
├── 10.19.220.10/
│   ├── enumeration/
│   │   ├── ports.json
│   │   ├── nmap_version_*.txt
│   │   ├── whatweb_*.txt
│   │   └── ...
│   ├── bitacora/
│   │   └── audit_20260930.log
│   └── findings/
│       ├── INDICE.md
│       └── FIND-*.md
├── 10.19.220.11/
│   └── ...
└── ...
```

## Troubleshooting

### "Could not connect to MCP Kali server"
```bash
# Check if Kali server is running
curl http://127.0.0.1:5001/health

# Start Kali server if needed
cd /opt/cline-mcps/MCP-Kali-Server
# (follow Kali server startup instructions)
```

### Audit seems stuck
```
# Check status
audit_status(project_id="<id>")

# Check last log entry
audit_get_bitacora(project_id="<id>", limit=10)
```

### Need to stop and resume
The audit automatically saves progress. Just run:
```
audit_run(project_id="<same-id>")
```

It will continue from where it stopped!

## What It Does

✅ **Enumerates:**
- Service versions
- Web technologies
- SSL/TLS configuration
- Available services
- Directory structure (fuzzing)

✅ **Detects:**
- CVEs (vulnerable versions)
- Anonymous access
- Default credentials
- Weak SSL/TLS
- Missing WAF

❌ **Does NOT:**
- Execute exploits
- Brute force passwords
- Perform DoS attacks
- Modify target systems

## Getting Help

1. **Check README.md** - Full documentation
2. **Check IMPLEMENTATION.md** - Technical details
3. **View logs:** `~/.local/share/audit-orchestrator/`
4. **SQLite DB:** `~/.local/share/audit-orchestrator/audit_state.db`

## Safety Notes

⚠️ **IMPORTANT:**
- Only use on authorized networks
- This is BLACK-BOX enumeration only
- No destructive operations
- All commands logged in bitacora
- Data stays local (100% on-premise)

---

```bash
# Un solo comando para todo
audit_start_and_run(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC",
    input_file="open_ports.txt",
    execution_mode="type_2_post_host_llm"
)
# Ver estado sin recordar el UUID
audit_status_by_path(base_path="/home/f0ns1/RedTeam/OCSR25/PoC")
# Continuar si se interrumpió
audit_resume(base_path="/home/f0ns1/RedTeam/OCSR25/PoC")
```
**Ready to start? Run the installation and configure your MCP client!**
