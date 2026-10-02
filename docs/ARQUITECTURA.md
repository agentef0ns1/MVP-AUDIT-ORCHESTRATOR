# Arquitectura - MVP Audit Orchestrator v2.0

## Visión General

Sistema de auditoría de seguridad automatizada con tres modos de ejecución: determinista (sin LLM), análisis post-host con LLM, y control total por LLM.

```
┌─────────────────────────────────────────────────────────────┐
│                     LLM (Externo)                           │
│  Analiza outputs, decide comandos, propone PoCs             │
└─────────────────┬───────────────────────────────────────────┘
                  │ MCP Tools
                  │
┌─────────────────▼───────────────────────────────────────────┐
│               MCP Server                                    │
│  Expone tools, valida parámetros, enruta solicitudes        │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│         Command Validator (Seguridad)                       │
│  Bloquea: DoS, brute-force, comandos destructivos          │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│           Audit Orchestrator                                │
│  - Type 1: Secuencia fija JSON                              │
│  - Type 2: JSON + LLM análisis + PoCs                       │
│  - Type 3: LLM control total (50 cmds, 30 min)             │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│               Kali MCP Client                               │
│  Wrapper para ejecución de herramientas                     │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│            Kali MCP Server                                  │
│  Ejecuta comandos en Kali Linux                             │
└─────────────────────────────────────────────────────────────┘
```

## Componentes Principales

### 1. MCP Server (`mcp_server/__init__.py`)

**Responsabilidad**: Interfaz MCP para interacción con LLM/agentes externos.

**Tools Expuestos**:
- `audit_start()` - Iniciar proyecto
- `audit_run()` - Ejecutar auditoría
- `audit_status()` - Estado del proyecto
- `audit_get_findings()` - Obtener hallazgos
- `audit_llm_analyze_host()` - Contexto para análisis LLM (Type 2)
- `audit_llm_execute_poc()` - Ejecutar PoC (Type 2)
- `audit_llm_get_context()` - Contexto actual (Type 3)
- `audit_llm_next_command()` - Ejecutar comando LLM (Type 3)

### 2. Audit Orchestrator (`core/orchestrator.py`)

**Responsabilidad**: Lógica central de orquestación de auditorías.

**Métodos Clave**:
- `start_audit()` - Parsear input, crear proyecto, estructura de directorios
- `run_audit()` - Loop principal de auditoría
- `_audit_target()` - Dispatcher por execution_mode
- `_audit_target_type1()` - Ejecución determinista
- `_audit_target_type2()` - Ejecución con análisis LLM post-host
- `_audit_target_type3()` - Ejecución con control total LLM
- `_build_host_context()` - Construir contexto para LLM

**Flujo Type 1** (No LLM):
```
parse input → crear servicios → por cada servicio:
  → obtener tasks del JSON → ejecutar tasks → guardar outputs
```

**Flujo Type 2** (Post-Host LLM):
```
igual que Type 1 → al terminar host:
  → construir contexto → marcar pending_llm_analysis
  → LLM llama audit_llm_analyze_host()
  → LLM propone y ejecuta PoCs con audit_llm_execute_poc()
```

**Flujo Type 3** (Full LLM):
```
crear proyecto → por cada target:
  → ejecutar bootstrap nmap -sV
  → crear llm_execution_state
  → LLM llama audit_llm_next_command() en loop
  → límites: 50 comandos o 30 minutos
```

### 3. Command Validator (`core/command_validator.py`)

**Responsabilidad**: Validar seguridad de comandos propuestos por LLM.

**Bloquea**:
- DoS: `hping3`, `slowloris`, loops infinitos
- Brute-force online: `hydra`, `medusa`, `ncrack`
- Destructivos: `rm -rf`, `dd`, `shutdown`, `mkfs`
- Peligrosos: `curl|sh`, `chmod 777`, download-execute

**Permite**:
- Reconnaissance: `nmap`, `masscan`
- Enumeration: `nikto`, `whatweb`, `gobuster`, `wpscan`
- PoCs seguros: `curl`, operaciones read-only

### 4. AuditStore (`core/store.py`)

**Responsabilidad**: Capa de persistencia sobre SQLite.

**Tablas**:
- `projects` - Proyectos de auditoría (incluye `execution_mode`)
- `targets` - Hosts/IPs a auditar
- `services` - Puertos por target
- `audit_tasks` - Tareas ejecutadas
- `bitacora_entries` - Log de operaciones
- `findings` - Vulnerabilidades detectadas
- `llm_execution_state` - Estado ejecución Type 3

### 5. Kali MCP Client (`core/kali_client.py`)

**Responsabilidad**: Wrapper para ejecutar comandos en Kali Server.

**Funciones**:
- `execute()` - Ejecutar comando con timeout
- Manejo de errores y reintentos
- Mapeo de respuesta del servidor

### 6. Parser (`core/parser.py`)

**Responsabilidad**: Parsear salida de nmap.

**Formatos Soportados**:
- Texto plano: `PORT/tcp open service`
- `Nmap scan report for X`
- `Discovered open port X/tcp on Y`
- JSON estructurado

**Detección SSL/TLS**:
- `ssl/http` → HTTPS
- `ssl/radan-http` → HTTPS
- `tls/http` → HTTPS
- `https` → HTTPS

### 7. Audit Profiles (`audit_profiles/default_blackbox.json`)

**Responsabilidad**: Definir tareas por tipo de servicio.

**Estructura**:
```json
{
  "profile_id": "default_blackbox",
  "tasks": {
    "http": [...],      // Tareas para HTTP
    "https": [...],     // Tareas para HTTPS (SSL/TLS)
    "ssh": [...],       // Tareas para SSH
    "all_services": [...] // Tareas para todos
  }
}
```

## Base de Datos (SQLite)

**Ubicación**: `~/.local/share/audit-orchestrator/audit_state.db`

**Schema Version**: 2

### Tablas Principales

**projects**:
```sql
- project_id (PK)
- base_path
- input_file
- profile
- execution_mode  -- 'type_1_no_llm', 'type_2_post_host_llm', 'type_3_interactive_llm'
- status
- created_at, updated_at, completed_at
```

**llm_execution_state** (nuevo en v2):
```sql
- state_id (PK)
- project_id (FK)
- target_id (FK)
- commands_executed  -- Contador para límite de 50
- execution_time_seconds  -- Tiempo para límite de 30 min
- last_command, last_output
- created_at, updated_at
```

## Modos de Ejecución

### Type 1: No LLM (Determinista)

```
Entrada: open_ports.txt
 ↓
Parser: detecta targets y servicios
 ↓
Orchestrator: por cada servicio
 ↓
Profile: obtiene tasks del JSON
 ↓
Kali Client: ejecuta comandos
 ↓
Store: guarda outputs y findings
 ↓
Salida: Estructura de directorios con resultados
```

**Características**:
- Rápido y predecible
- Sin dependencias externas (LLM)
- Perfecto para CI/CD

### Type 2: Post-Host LLM

```
[Igual que Type 1 hasta completar todos los servicios del host]
 ↓
Orchestrator: marca pending_llm_analysis
 ↓
LLM: llama audit_llm_analyze_host()
 ↓
LLM: analiza outputs, correlaciona findings
 ↓
LLM: propone PoCs seguros
 ↓
LLM: ejecuta con audit_llm_execute_poc()
 ↓
Command Validator: verifica seguridad
 ↓
Kali Client: ejecuta PoCs
 ↓
Store: guarda resultados PoCs
```

**Características**:
- Análisis inteligente post-enumeración
- PoCs contextuales
- Ejecución automática de PoCs

### Type 3: Interactive LLM

```
Entrada: open_ports.txt
 ↓
Parser: detecta targets
 ↓
Orchestrator: ejecuta bootstrap nmap -sV
 ↓
LLM: llama audit_llm_get_context()
 ↓
LLM: decide siguiente comando basado en outputs
 ↓
LLM: ejecuta con audit_llm_next_command()
 ↓
Command Validator: verifica seguridad
 ↓
Kali Client: ejecuta
 ↓
Store: actualiza llm_execution_state
 ↓
[Repite hasta límites: 50 comandos o 30 minutos]
```

**Características**:
- Máxima adaptabilidad
- LLM decide cada paso
- Límites estrictos de seguridad

## Seguridad

### Validación de Comandos

Todos los comandos en Type 2 y Type 3 pasan por `validate_safe_command()`:

```python
def validate_safe_command(command: str) -> tuple[bool, str]:
    # Verifica contra BLOCKED_COMMANDS y BLOCKED_PATTERNS
    # Retorna (is_safe, reason)
```

### Restricciones del Proyecto

**Prohibido**:
- ❌ Ataques DoS
- ❌ Brute-force online
- ❌ Operaciones destructivas
- ❌ Manipulación de sistema

**Permitido**:
- ✅ Reconnaissance
- ✅ Enumeration
- ✅ PoCs no-destructivos
- ✅ Verificación de vulnerabilidades

### Límites Type 3

- **Comandos**: Máximo 50 por target
- **Tiempo**: Máximo 30 minutos por target
- **Validación**: Cada comando validado antes de ejecutar

## Extensibilidad

### Añadir Nuevo Servicio al Profile

Editar `audit_profiles/default_blackbox.json`:

```json
{
  "tasks": {
    "nuevo_servicio": [
      {
        "type": "tool_name",
        "command": "tool {target}:{port}",
        "description": "What this does"
      }
    ]
  }
}
```

### Añadir Nuevo MCP Tool

En `mcp_server/__init__.py`:

```python
@mcp.tool(structured_output=False)
def nuevo_tool(param1: str, param2: int) -> str:
    """Descripción del tool"""
    def _impl():
        # Lógica
        return {"result": "data"}
    
    return _handle(_impl)
```

### Añadir Validación Custom

En `command_validator.py`:

```python
# Agregar a BLOCKED_COMMANDS o BLOCKED_PATTERNS
BLOCKED_COMMANDS.append("comando_peligroso")
BLOCKED_PATTERNS.append(r"patron_regex")
```

## Performance

### Type 1
- **Setup**: ~1s
- **Por servicio**: ~5-10 min
- **Por target**: ~15-30 min (3-5 servicios)
- **Recursos**: Low CPU, low memory

### Type 2
- **Enum**: Igual que Type 1
- **Análisis LLM**: +2-5 min por target
- **PoCs**: +5-10 min por target
- **Total**: Type 1 + 7-15 min
- **Recursos**: Medium CPU, medium memory + LLM API

### Type 3
- **Bootstrap**: ~2-5 min
- **Loop LLM**: Hasta 30 min por target
- **Comandos**: 1-50 por target
- **Recursos**: High CPU, high memory + muchas llamadas LLM

## Dependencias

**Requeridas**:
- Python 3.10+
- SQLite 3
- FastMCP
- Kali MCP Server (http://127.0.0.1:5001)

**Opcionales**:
- LLM con soporte MCP (para Type 2/3)

## Estructura de Directorios

```
MVP-audit-orchestrator/
├── src/audit_orchestrator/
│   ├── core/
│   │   ├── db.py                    # Schema SQLite
│   │   ├── store.py                 # Capa de persistencia
│   │   ├── orchestrator.py          # Lógica principal
│   │   ├── kali_client.py           # Cliente Kali MCP
│   │   ├── parser.py                # Parser nmap
│   │   ├── filesystem.py            # Gestión directorios
│   │   ├── command_validator.py     # Validación seguridad
│   │   └── tool_installer.py        # Auto-instalación tools
│   ├── audit_profiles/
│   │   └── default_blackbox.json    # Profile de tareas
│   └── mcp_server/
│       └── __init__.py              # Servidor MCP
├── scripts/
│   ├── check_project_status.py     # Inspección proyecto
│   ├── delete_project_completely.py # Limpieza completa
│   ├── list_all_projects.py        # Listar proyectos
│   ├── reset_database_completely.py # Reset DB
│   └── reset_project.py             # Reset proyecto
├── dev-tools/                       # Scripts de desarrollo
│   ├── test_*.py                    # Tests
│   ├── verify_installation.py      # Verificación
│   └── migrate_database.py          # Migración manual
└── docs/
    ├── ARQUITECTURA.md              # Este archivo
    ├── INSTALACION.md               # Setup
    ├── USO_RAPIDO.md                # Quick start
    └── ARQUITECTURA_CON_LLM.md      # Detalles LLM (legacy)
```

## Versiones

**v1.0**: MVP inicial, solo Type 1 (no LLM)
**v2.0**: Añadido Type 2 y 3, validador, fix SSL/TLS

---

**Versión**: 2.0.0  
**Última actualización**: 2026-10-01
