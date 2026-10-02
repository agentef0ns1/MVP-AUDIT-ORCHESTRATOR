# Changelog

## [2.4.0] - 2026-10-01

### Added - Global audit.log with Target Traceability

**Problem**: `audit.log` lost target/IP traceability when auditing multiple hosts. When reviewing logs, it was unclear which lines belonged to which target.

**Solution**: Dual logging system:
- **Target-specific log**: `<target>/bitacora/audit_YYYYMMDD.log` (unchanged)
- **Global log**: `audit.log` in base_path with `[TARGET]` prefix on each line (NEW)

**New Format**:
```
[2026-10-01 10:30:15] [10.19.220.23] SERVICE: 8088/tcp (radan-http)
[2026-10-01 10:30:15] [10.19.220.23] Checking for SSL/TLS...
[2026-10-01 10:30:20] [10.19.220.23] ✓ SSL/TLS detected - using HTTPS
[2026-10-01 10:30:20] [10.19.220.23] COMMAND: whatweb https://10.19.220.23:8088
[2026-10-01 10:30:25] [10.19.220.24] SERVICE: 22/tcp (ssh)
```

**Benefits**:
- ✅ Every line shows target clearly
- ✅ Easy grep by target: `grep '\[10.19.220.23\]' audit.log`
- ✅ See all targets in one consolidated file
- ✅ Useful for real-time monitoring: `tail -f audit.log | grep '\[target\]'`
- ✅ Works perfectly with SSL detection logging

**Usage**:
```bash
# Monitor all activity
tail -f /path/to/audit/audit.log

# Monitor specific target
tail -f audit.log | grep '\[10.19.220.23\]'

# Find SSL detections
grep -i 'SSL detected' audit.log

# Find all commands executed
grep 'COMMAND:' audit.log
```

**Impact**: Negligible performance (~1-2ms per line), fully backward compatible

**Files Changed**:
- `filesystem.py` - Modified `append_bitacora()` to write to both logs

---

## [2.3.0] - 2026-10-01

### Changed - SSL Detection Strategy (Runtime Detection)

**Old approach (v0.2.2)**: Detect SSL from nmap scripts during parsing.  
**Problem**: Required regenerating `open_ports.txt` with `nmap -sC`, expensive for many IPs.

**New approach (v0.2.3)**: Detect SSL at **runtime** during audit, just before attacking each web port.

**How it works**:
- When orchestrator finds HTTP service without SSL prefix
- Tests SSL with: `openssl s_client -connect host:port`
- If SSL detected → uses `https` profile tasks
- If no SSL → uses `http` profile tasks
- Each detection logged in bitácora

**Benefits**:
- ✅ No need to regenerate input files
- ✅ Accurate real-time SSL detection via openssl test
- ✅ Automatic HTTP vs HTTPS decision
- ✅ Logged in audit.log and bitácora
- ✅ Works with existing `open_ports.txt` files

**Impact**:
- +5-10 seconds per HTTP port (SSL test overhead)
- No changes to input file format required
- No database migration needed
- Fully backward compatible

**Files Changed**:
- `orchestrator.py` - Added `_detect_ssl_on_port()` method
- `orchestrator.py` - Modified `_audit_service()` for runtime detection
- `parser.py` - Reverted parsing-time SSL enrichment

---

## [2.2.0] - 2026-10-01

### Fixed - SSL/HTTPS Detection from Nmap Scripts (REVERTED in v0.2.3)

**Problem**: El sistema usaba HTTP en lugar de HTTPS incluso cuando nmap reportaba certificados SSL y redirects HTTPS en los scripts.

**Root Cause**: El parser solo detectaba SSL cuando el servicio tenía prefijo `ssl/` en el nombre (ej: `ssl/radan-http`). Si el input file tenía `radan-http` sin scripts, no detectaba SSL.

**Solution**: 
- Añadida función `_enrich_ssl_detection()` que analiza el output completo de nmap
- Detecta indicadores SSL en scripts: `ssl-cert`, `ssl-date`, `https://`, `TLS`, `SSL`, `certificate`
- Marca automáticamente servicios HTTP como `ssl/http` cuando encuentra contexto SSL

**Testing**:
- ✅ Nuevo test suite: `dev-tools/test_ssl_detection_from_scripts.py`
- ✅ 3/3 tests passing (SSL from scripts, SSL from name, no false positives)

**User Action Required**:
⚠️  Archivos `open_ports.txt` existentes sin scripts deben regenerarse con:
```bash
nmap -sV -sC <target> -oN open_ports.txt
```

**Helper Script**:
- `scripts/regenerate_with_ssl_detection.sh` - Regenera nmap con SSL detection

**Files Changed**:
- `src/audit_orchestrator/core/parser.py` - Added `_enrich_ssl_detection()`

**Backward Compatible**: ✅ Sí, archivos existentes siguen funcionando

---

## [2.1.0] - 2026-10-01

### Added - Convenience Tools (Sin project_id)

**Problema resuelto**: Los modelos LLM tenían que manejar UUIDs entre llamadas (`audit_start` → copiar project_id → `audit_run`), causando errores y complejidad innecesaria.

**Nuevas herramientas**:

#### `audit_start_and_run()`
Combina `audit_start()` + `audit_run()` en una sola llamada.

```python
# Antes (2 pasos, necesitas copiar UUID)
result = audit_start(base_path="/tmp/audit", input_file="open_ports.txt")
project_id = result["project_id"]  # ← modelo tiene que extraer esto
audit_run(project_id=project_id)   # ← y usarlo aquí

# Ahora (1 paso, sin UUID)
audit_start_and_run(
    base_path="/tmp/audit",
    input_file="open_ports.txt",
    execution_mode="type_2_post_host_llm"
)
```

**Beneficios**:
- ✅ Reduce carga cognitiva del modelo
- ✅ Evita errores de copy/paste de UUIDs
- ✅ Workflow más natural
- ✅ Menos tokens usados

#### `audit_resume()`
Continúa auditoría existente solo con el directorio.

```python
# Continuar auditoría interrumpida o añadir más targets
audit_resume(base_path="/tmp/audit")
```

**Casos de uso**:
- Auditoría interrumpida (error, timeout, manual)
- Re-ejecutar después de reset
- Procesar más targets sin buscar UUID

#### `audit_status_by_path()`
Obtiene estado sin necesitar project_id.

```python
# Ver estado solo con directorio
audit_status_by_path(base_path="/tmp/audit")
```

### Changed

**store.py**:
- Añadido `get_project_by_path()` - Busca proyecto por base_path + input_file

**mcp_server/__init__.py**:
- 3 nuevos MCP tools registrados
- Todos validados y testeados

### Testing

Nuevo test suite: `dev-tools/test_convenience_tools.py`
- ✅ Test `get_project_by_path()`
- ✅ Test MCP tools registration
- ✅ Test signatures completas

### Documentation

**Actualizado**:
- `README.md` - Muestra métodos simples primero
- `docs/USO_RAPIDO.md` - Sección "Comandos Sin project_id"
- Lista de MCP tools reorganizada (simples primero)

---

## [2.0.0] - 2026-10-01

### Added - LLM Integration

**3 Modos de Ejecución**:
1. **Type 1**: Sin LLM (determinista, secuencia JSON fija)
2. **Type 2**: LLM analiza post-host y ejecuta PoCs
3. **Type 3**: LLM control total (50 cmds, 30 min límites)

**Nuevos MCP Tools**:
- `audit_llm_analyze_host()` - Type 2: Contexto host
- `audit_llm_execute_poc()` - Type 2: Ejecutar PoC
- `audit_llm_get_context()` - Type 3: Estado actual
- `audit_llm_next_command()` - Type 3: Ejecutar comando LLM

**Seguridad**:
- Command validator (`command_validator.py`)
- Bloquea: DoS, brute-force, destructivos
- Límites Type 3: 50 comandos, 30 minutos

**Base de Datos**:
- Schema v1 → v2
- Campo `execution_mode` en tabla `projects`
- Nueva tabla `llm_execution_state` (Type 3 tracking)

### Fixed

**Parser nmap**:
- Soporte formato "Nmap scan report for X"
- Antes solo reconocía líneas con solo la IP

**Detección SSL/HTTPS**:
- `ssl/radan-http` → HTTPS ✅
- `ssl/http` → HTTPS ✅
- `tls/http` → HTTPS ✅
- `ssl/http-alt` → HTTPS ✅

Antes estos servicios usaban HTTP erróneamente.

**Migración DB**:
- Migración robusta que verifica columnas existentes
- No falla si `execution_mode` ya existe
- Auto-migración al iniciar servidor

### Changed

**orchestrator.py**:
- `start_audit()` acepta `execution_mode`
- `_audit_target()` dispatcher por modo
- Nuevos métodos: `_audit_target_type1/2/3()`
- Nuevo método: `_build_host_context()`

**mcp_server/__init__.py**:
- `audit_start()` acepta `execution_mode`
- 4 nuevos tools para LLM

### Documentation

**Nuevos documentos**:
- `docs/ARQUITECTURA.md` - Arquitectura del sistema
- `docs/INSTALACION.md` - Setup y troubleshooting
- `docs/USO_RAPIDO.md` - Guía rápida
- `README.md` - Índice principal

**Reorganizado**:
- `docs/` - Solo 3 docs principales para usuarios
- `dev-tools/` - Scripts de testing y desarrollo
- `scripts/` - Scripts de usuario (reset, delete, etc.)

**Eliminado**:
- Documentación redundante consolidada

---

## [1.0.0] - 2026-09-30

### Initial Release

**Core Features**:
- Orquestación de auditorías automatizadas
- Parser de nmap (texto y JSON)
- Perfiles de tareas por servicio
- Ejecución via Kali MCP Server
- Base de datos SQLite para state
- Workspace filesystem estructurado
- MCP tools para integración con LLM/agentes

**Database**:
- Schema v1
- Tablas: projects, targets, services, audit_tasks, bitacora_entries, findings

**Supported Services**:
- HTTP, HTTPS, SSH, FTP, SMB, SMTP, MySQL, PostgreSQL
- All services (nmap version, nmap scripts)

**Tools**:
- `audit_start()` - Iniciar proyecto
- `audit_run()` - Ejecutar auditoría
- `audit_status()` - Ver estado
- `audit_get_findings()` - Obtener hallazgos
- `audit_get_targets()` - Listar targets
- `audit_get_bitacora()` - Ver log
- `audit_finalize()` - Finalizar proyecto

**Scripts**:
- `list_all_projects.py` - Listar proyectos
- `check_project_status.py` - Ver estado
- `delete_project_completely.py` - Eliminar proyecto
- `reset_database_completely.py` - Reset DB
- `reset_project.py` - Reset proyecto

---

## Version Format

`[MAJOR.MINOR.PATCH]`

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

---

**Mantenido por**: Security Team  
**Repositorio**: MVP Audit Orchestrator
