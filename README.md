# MVP Audit Orchestrator

Sistema de auditoría de seguridad automatizada con integración LLM opcional y **ejecución paralela de targets**.

**Versión actual**: 0.3.0 | **Última actualización**: 2026-10-02

## 📚 Documentación

### 🚀 Inicio Rápido
- **[QUICK_START.md](QUICK_START.md)** - Guía rápida de inicio (inglés)
- **[docs/USO_RAPIDO.md](docs/USO_RAPIDO.md)** - Guía rápida de uso (español)

### 📖 Documentación Completa
- **[docs/](docs/)** - Índice completo de documentación
  - [INSTALACION.md](docs/INSTALACION.md) - Instalación y configuración
  - [CONFIGURACION.md](docs/CONFIGURACION.md) - **Configuración (puerto Kali, concurrencia, etc.)** ⭐
  - [ARQUITECTURA.md](docs/ARQUITECTURA.md) - Arquitectura del sistema
  - [PARALLEL_EXECUTION.md](docs/PARALLEL_EXECUTION.md) - **Ejecución paralela y sistema de revisión** ⭐ **NUEVO**
  - [FORMATOS_NMAP.md](docs/FORMATOS_NMAP.md) - Entrada nmap: normal, grepable, XML y bucle for
  - [IMPLEMENTATION.md](docs/IMPLEMENTATION.md) - Detalles técnicos
  - [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Solución de problemas
  - [CHANGELOG.md](docs/CHANGELOG.md) - Changelog completo

### 🛠️ Para Desarrolladores
- **[dev-tools/](dev-tools/)** - Herramientas de desarrollo y testing

## 🚀 Inicio Rápido

### 1. Instalar

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
pip install -e .
```

### 2. Configurar MCP en Cursor

Editar `~/.cursor/mcp_servers.json`:

```json
{
  "mcpServers": {
    "audit-orchestrator": {
      "command": "python3",
      "args": [
        "-m", "audit_orchestrator.mcp_server",
        "--transport", "stdio",
        "--kali-server-url", "http://127.0.0.1:5001"
      ],
      "env": {
        "AUDIT_MAX_CONCURRENT": "10",
        "AUDIT_AUTO_REVIEW": "true"
      },
      "cwd": "/opt/cline-mcps/MVP-audit-orchestrator"
    }
  }
}
```

**Configuración del puerto Kali**:
- Cambiar `--kali-server-url` para usar otro puerto u host
- Ver [CONFIGURACION.md](docs/CONFIGURACION.md) para todas las opciones

### 3. Usar

Desde Cursor chat:

```python
# Método simple (recomendado) - todo en uno
audit_start_and_run(
    base_path="/tmp/audit",
    input_file="open_ports.txt"
)

# O método tradicional (2 pasos)
audit_start(base_path="/tmp/audit", input_file="open_ports.txt")
audit_run(project_id="abc-123")

# Ver resultados (con o sin project_id)
audit_status_by_path(base_path="/tmp/audit")
```

Ver **[docs/USO_RAPIDO.md](docs/USO_RAPIDO.md)** para más ejemplos.

## ✨ Características

### 🚀 Ejecución Paralela (v0.3.0)

- **10x más rápido**: Procesa múltiples targets simultáneamente
- **Concurrencia configurable**: Ajusta `max_concurrent` según tu infraestructura (default: 10)
- **Auto-review inteligente**: Detecta auditorías fallidas automáticamente
- **Reportes por servicios**: Agrupa targets por HTTP, SSH, MySQL, etc.
- **Re-encolado automático**: Vuelve a intentar targets que fallaron

```python
# Ejecutar con 15 targets en paralelo
audit_run(project_id="abc-123", parallel=true, max_concurrent=15)

# Revisar y re-encolar fallos
audit_review(project_id="abc-123", re_enqueue_failed=true)
```

Ver **[docs/PARALLEL_EXECUTION.md](docs/PARALLEL_EXECUTION.md)** para más detalles.

### Tres Modos de Ejecución

1. **Type 1: Sin LLM** (default)
   - Rápido y determinista
   - Secuencia fija del profile JSON
   - Perfecto para CI/CD

2. **Type 2: LLM Post-Host**
   - Ejecuta enumeración completa
   - LLM analiza resultados
   - Propone y ejecuta PoCs automáticamente

3. **Type 3: LLM Control Total**
   - LLM decide cada comando
   - Máxima adaptabilidad
   - Límites: 50 comandos, 30 min por target

### Detección Automática SSL/HTTPS

```
Input nmap:
  8088/tcp open ssl/radan-http myServer

Detección:
  ✅ Usa HTTPS automáticamente
  ✅ Ejecuta sslscan, testssl
  ✅ Fuzzing con https://
```

### Seguridad

- ✅ Validación de comandos LLM
- ✅ Bloquea DoS, brute-force, destructivos
- ✅ Límites estrictos en modo Type 3
- ✅ Ejecución aislada en Kali MCP Server

## 📋 Requisitos

- Python 3.10+
- SQLite 3
- Kali MCP Server (http://127.0.0.1:5001)
- Cursor IDE (para interfaz MCP)

## 🛠️ Scripts Útiles

```bash
# Listar proyectos
python3 scripts/list_all_projects.py

# Ver estado de proyecto
python3 scripts/check_project_status.py <project_id>

# Reset proyecto
python3 scripts/reset_project.py <project_id>

# Eliminar proyecto
python3 scripts/delete_project_completely.py <project_id>

# Verificar instalación (dev)
python3 dev-tools/verify_installation.py
```

## 📁 Estructura del Proyecto

```
MVP-audit-orchestrator/
├── README.md                # Este archivo
├── QUICK_START.md           # Guía de inicio rápido
│
├── docs/                    # 📚 Documentación completa
│   ├── README.md            # Índice de documentación
│   ├── INSTALACION.md       # Instalación
│   ├── USO_RAPIDO.md        # Guía de uso (ES)
│   ├── ARQUITECTURA.md      # Arquitectura
│   ├── IMPLEMENTATION.md    # Detalles técnicos
│   ├── TROUBLESHOOTING.md   # Solución de problemas
│   ├── CHANGELOG.md         # Historial completo
│   └── CHANGELOG_v0.2.5.md  # Changelog v0.2.5
│
├── src/audit_orchestrator/  # Código fuente
│   ├── core/                # Lógica principal
│   │   ├── orchestrator.py  # Orquestador de auditorías
│   │   ├── filesystem.py    # Gestión de archivos
│   │   ├── kali_client.py   # Cliente Kali MCP
│   │   └── command_validator.py  # Validación comandos
│   ├── audit_profiles/      # Perfiles de auditoría
│   │   ├── default_blackbox.json
│   │   ├── default_blackbox_fast.json
│   │   └── default_blackbox_web_intensive.json
│   └── mcp_server/          # Servidor MCP
│
├── scripts/                 # Scripts de usuario
│   ├── list_all_projects.py
│   ├── check_project_status.py
│   ├── reset_project.py
│   └── delete_project_completely.py
│
└── dev-tools/               # 🛠️ Herramientas de desarrollo
    ├── README.md            # Índice de herramientas
    ├── verify_installation.py
    ├── test_profile_parsing.py
    ├── migrate_database.py
    └── LLM_EXECUTION_MODES.md
```

## 🔧 Troubleshooting

Si encuentras problemas, consulta **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** para soluciones detalladas.

Problemas comunes:
- Error MCP "Connection closed" → Migrar BD y reiniciar
- SSL services usan HTTP → Verificar detección SSL
- Comandos bloqueados → Revisar command validator

Ver la guía completa: **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**

## 📊 MCP Tools Disponibles

### Simples (sin project_id) ⭐ Recomendados
- `audit_start_and_run()` - Start + Run en un comando
- `audit_resume()` - Continuar desde directorio
- `audit_status_by_path()` - Ver estado sin UUID

### Básicos
- `audit_start()` - Iniciar proyecto
- `audit_run()` - Ejecutar auditoría
- `audit_status()` - Ver estado
- `audit_get_findings()` - Obtener hallazgos
- `audit_get_targets()` - Listar targets
- `audit_get_bitacora()` - Ver log
- `audit_reset_project()` - Reset proyecto
- `audit_finalize()` - Finalizar proyecto

### LLM (Type 2)
- `audit_llm_analyze_host()` - Obtener contexto host
- `audit_llm_execute_poc()` - Ejecutar PoC

### LLM (Type 3)
- `audit_llm_get_context()` - Obtener estado actual
- `audit_llm_next_command()` - Ejecutar comando LLM

## 🔄 Actualización

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
git pull origin main
pip install -e . --force-reinstall
# Reiniciar Cursor
```

La migración de DB es automática.

## 📝 Changelog

### v0.2.5 (2026-10-02) - Audit Profile Enhancement

**Major enhancements to audit profiles:**
- 🎯 **101 total tasks** (from ~30) in default_blackbox.json
- 🆕 **6 new services**: MongoDB, Redis, Elasticsearch, Docker, Kubernetes, Jenkins
- 🔍 **27 finding rules** (from 5) for vulnerability detection
- 📦 **3 profile variants**: fast, full, web_intensive
- 🛡️ **38 reconnaissance tools** whitelisted in command validator

Ver **[docs/CHANGELOG_v0.2.5.md](docs/CHANGELOG_v0.2.5.md)** para detalles completos.

### Versiones Anteriores

Ver **[docs/CHANGELOG.md](docs/CHANGELOG.md)** para el historial completo.

---

## 📄 Licencia

Ver LICENSE file.

---

**Versión actual**: 0.2.5  
**Última actualización**: 2026-10-02
