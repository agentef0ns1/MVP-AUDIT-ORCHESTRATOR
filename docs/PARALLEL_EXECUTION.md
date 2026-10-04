# Ejecución Paralela y Sistema de Revisión de Auditorías

Esta guía documenta el sistema de ejecución paralela de auditorías y el sistema de revisión automática que detecta fallos y genera reportes de servicios.

## Tabla de Contenidos

- [Introducción](#introducción)
- [Ejecución Paralela](#ejecución-paralela)
- [Sistema de Revisión](#sistema-de-revisión)
- [Ejemplos de Uso](#ejemplos-de-uso)
- [Configuración](#configuración)
- [Troubleshooting](#troubleshooting)
- [Métricas de Rendimiento](#métricas-de-rendimiento)

---

## Introducción

A partir de la versión `0.3.0`, el audit orchestrator soporta **ejecución paralela** de targets, permitiendo auditar múltiples máquinas simultáneamente con un límite configurable de concurrencia.

Además, incluye un **sistema de revisión automática** que:
- Detecta auditorías fallidas por problemas de conectividad o errores
- Re-encola targets fallidos automáticamente
- Genera reportes agrupando máquinas por servicios detectados

### Ventajas

- **10x más rápido**: Auditar 100 targets en paralelo vs secuencial
- **Detección automática de fallos**: No pierdas tiempo con targets que fallaron silenciosamente
- **Reportes de servicios**: Agrupa y visualiza targets por servicios (HTTP, SSH, MySQL, etc.)
- **Configurable**: Ajusta la concurrencia según tu infraestructura

---

## Ejecución Paralela

### Cómo Funciona

El sistema usa `asyncio` con semaphores para controlar la concurrencia:

```python
# Limitar a 10 targets concurrentes
semaphore = asyncio.Semaphore(10)

# Ejecutar todos los targets en paralelo con el límite
tasks = [audit_target(target) for target in targets]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

El cliente HTTP (`httpx.AsyncClient`) soporta múltiples requests concurrentes nativamente, lo que permite que el servidor Kali MCP procese varias auditorías simultáneamente.

### Parámetros

| Parámetro | Tipo | Default | Descripción |
|-----------|------|---------|-------------|
| `parallel` | bool | `true` | Habilitar ejecución paralela |
| `max_concurrent` | int | `10` | Máximo de targets concurrentes |
| `auto_review` | bool | `true` | Ejecutar revisión automática antes de empezar |

### Variables de Entorno

```bash
# Configuración por defecto
export AUDIT_MAX_CONCURRENT=10
export AUDIT_AUTO_REVIEW=true
export AUDIT_ERROR_THRESHOLD=0.8
```

---

## Sistema de Revisión

### Criterios de Detección de Fallos

Una auditoría se considera **fallida** si cumple alguno de estos criterios:

1. **No existe directorio bitacora**
2. **Bitacora vacía** (no hay log files o están vacíos)
3. **Más del 80% de líneas son errores** detectando keywords:
   - "connection refused"
   - "connection timed out"
   - "no route to host"
   - "host is down"
   - "unreachable"
   - "failed", "error", "timeout"
4. **Outputs de enumeración vacíos** (todos los archivos < 100 bytes)

### Re-encolado Automático

Cuando se detecta un fallo, el target se **resetea a estado "pending"** y puede volver a ejecutarse en la siguiente run.

### Reporte de Servicios

El sistema genera `SERVICES_REPORT.md` agrupando targets por servicios:

```markdown
# Services Report

## HTTP (ports: 80, 443, 8080)

**Total machines**: 15

### Completed (12)
- `10.1.1.1:80`
- `10.1.1.2:443`
...

### Failed/Timeout (3)
- `10.1.1.10:8080` - timeout
...

## SSH (ports: 22)
...
```

---

## Ejemplos de Uso

### Ejemplo 1: Ejecución Paralela Básica (MCP Tool)

```json
{
  "tool": "audit_start_and_run",
  "arguments": {
    "base_path": "/tmp/audit-project",
    "input_file": "open_ports.txt",
    "parallel": true,
    "max_concurrent": 10
  }
}
```

**Resultado:**
```json
{
  "done": true,
  "project_id": "abc-123",
  "targets_processed": 50,
  "targets_completed": 48,
  "targets_failed": 2,
  "duration": 245.3,
  "parallel": true,
  "max_concurrent": 10,
  "re_enqueued": 2
}
```

### Ejemplo 2: Alta Concurrencia

```json
{
  "tool": "audit_run",
  "arguments": {
    "project_id": "abc-123",
    "parallel": true,
    "max_concurrent": 25
  }
}
```

**Uso:** Cuando tienes una máquina potente y quieres maximizar velocidad.

### Ejemplo 3: Modo Secuencial (Legacy)

```json
{
  "tool": "audit_run",
  "arguments": {
    "project_id": "abc-123",
    "parallel": false
  }
}
```

**Uso:** Debugging, compatibilidad, o recursos limitados.

### Ejemplo 4: Revisión Manual sin Re-encolado

```json
{
  "tool": "audit_review",
  "arguments": {
    "project_id": "abc-123",
    "re_enqueue_failed": false
  }
}
```

**Resultado:**
```json
{
  "total_targets": 100,
  "failed_targets": [
    {
      "ip": "10.1.1.50",
      "reason": "Too many errors in bitacora (45/50 lines)"
    }
  ],
  "re_enqueued": 0,
  "report_path": "/tmp/audit-project/SERVICES_REPORT.md"
}
```

### Ejemplo 5: Revisión con Re-encolado Automático

```json
{
  "tool": "audit_review",
  "arguments": {
    "project_id": "abc-123",
    "re_enqueue_failed": true
  }
}
```

**Resultado:**
```json
{
  "total_targets": 100,
  "failed_targets": [
    {
      "ip": "10.1.1.50",
      "reason": "Too many errors in bitacora (45/50 lines)"
    },
    {
      "ip": "10.1.1.75",
      "reason": "Empty bitacora file"
    }
  ],
  "re_enqueued": 2,
  "report_path": "/tmp/audit-project/SERVICES_REPORT.md"
}
```

### Ejemplo 6: Pipeline Completo

```json
// 1. Iniciar y ejecutar
{
  "tool": "audit_start_and_run",
  "arguments": {
    "base_path": "/tmp/pentest-2024",
    "input_file": "targets.txt",
    "parallel": true,
    "max_concurrent": 15,
    "max_targets": 50
  }
}

// 2. Revisar y re-encolar fallos
{
  "tool": "audit_review",
  "arguments": {
    "project_id": "abc-123",
    "re_enqueue_failed": true
  }
}

// 3. Re-ejecutar solo los fallidos
{
  "tool": "audit_run",
  "arguments": {
    "project_id": "abc-123",
    "parallel": true,
    "max_concurrent": 5
  }
}

// 4. Generar resumen final
{
  "tool": "audit_generate_resumen",
  "arguments": {
    "project_id": "abc-123"
  }
}
```

### Ejemplo 7: Test Script - Ejecución Paralela

```bash
# Listar proyectos disponibles
python3 dev-tools/test_parallel_execution.py

# Ejecutar proyecto con 10 threads
python3 dev-tools/test_parallel_execution.py abc-123 10

# Ejecutar con alta concurrencia
python3 dev-tools/test_parallel_execution.py abc-123 25
```

**Salida esperada:**
```
======================================================================
Testing Parallel Audit Execution
======================================================================

Project ID: abc-123
Base Path: /tmp/audit-project
Profile: default_blackbox
Max Concurrent: 10

Pending targets: 50

Starting parallel execution...

======================================================================
Execution Results
======================================================================

✅ Completed: 48
❌ Failed: 2
📊 Total processed: 50
🔍 Services audited: 150
🚨 Findings created: 25
🔄 Re-enqueued: 2

⏱️  Duration: 245.30 seconds
🚀 Parallel: True
🔢 Concurrency: 10

📈 Average time per target: 4.91s

======================================================================
```

### Ejemplo 8: Test Script - Revisor de Auditorías

```bash
# Listar proyectos
python3 dev-tools/test_audit_reviewer.py

# Revisar sin re-encolar
python3 dev-tools/test_audit_reviewer.py abc-123

# Revisar y re-encolar
python3 dev-tools/test_audit_reviewer.py abc-123 --re-enqueue
```

**Salida esperada:**
```
======================================================================
Testing Audit Reviewer
======================================================================

Project ID: abc-123
Base Path: /tmp/audit-project
Re-enqueue failed: True

Reviewing project...

======================================================================
Review Results
======================================================================

Total targets: 100
Failed targets detected: 5
Re-enqueued: 5

Failed Targets:
----------------------------------------------------------------------
  • 10.1.1.50 (completed)
    Reason: Too many errors in bitacora (45/50 lines)

  • 10.1.1.75 (completed)
    Reason: Empty bitacora file

  • 10.1.1.88 (failed)
    Reason: No bitacora directory found

======================================================================
Services Report Generated
======================================================================

Report saved to: /tmp/audit-project/SERVICES_REPORT.md
```

### Ejemplo 9: Workflow con Auto-Review Deshabilitado

```json
// Ejecutar sin auto-review (para debugging)
{
  "tool": "audit_run",
  "arguments": {
    "project_id": "abc-123",
    "parallel": true,
    "max_concurrent": 10
  }
}

// Luego ejecutar review manualmente
{
  "tool": "audit_review",
  "arguments": {
    "project_id": "abc-123",
    "re_enqueue_failed": true
  }
}
```

### Ejemplo 10: Modo Progresivo

```json
// 1. Primera ejecución conservadora
{
  "tool": "audit_run",
  "arguments": {
    "project_id": "abc-123",
    "parallel": true,
    "max_concurrent": 5,
    "max_targets": 10
  }
}

// 2. Si funciona bien, aumentar concurrencia
{
  "tool": "audit_run",
  "arguments": {
    "project_id": "abc-123",
    "parallel": true,
    "max_concurrent": 15,
    "max_targets": 50
  }
}

// 3. Finalmente, procesar todo
{
  "tool": "audit_run",
  "arguments": {
    "project_id": "abc-123",
    "parallel": true,
    "max_concurrent": 20
  }
}
```

### Ejemplo 11: Integración con Python SDK

```python
import asyncio
from audit_orchestrator.core.orchestrator import AuditOrchestrator
from audit_orchestrator.core.store import AuditStore
from audit_orchestrator.config import Settings

async def parallel_audit():
    settings = Settings.from_args()
    store = AuditStore(settings)
    orch = AuditOrchestrator(settings, store)
    
    # Crear proyecto
    project = await orch.start_audit(
        base_path="/tmp/pentest",
        input_file="targets.txt",
        profile="default_blackbox"
    )
    
    # Ejecutar en paralelo
    result = await orch.run_audit_parallel(
        project_id=project["project_id"],
        max_concurrent=15,
        auto_review=True
    )
    
    print(f"Completed: {result['targets_completed']}")
    print(f"Duration: {result['duration']:.2f}s")

asyncio.run(parallel_audit())
```

### Ejemplo 12: Automatización con Script Bash

```bash
#!/bin/bash
# automated-audit.sh

PROJECT_ID="$1"
MAX_CONCURRENT="${2:-10}"

echo "Starting parallel audit: $PROJECT_ID"

# Ejecutar audit
curl -X POST http://localhost:5001/mcp/audit_run \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"parallel\": true,
    \"max_concurrent\": $MAX_CONCURRENT
  }"

# Esperar a que termine
sleep 10

# Revisar y generar reporte
curl -X POST http://localhost:5001/mcp/audit_review \
  -H "Content-Type: application/json" \
  -d "{
    \"project_id\": \"$PROJECT_ID\",
    \"re_enqueue_failed\": true
  }"

echo "Audit completed. Report: /tmp/audit/SERVICES_REPORT.md"
```

---

## Configuración

### En Python (Settings)

```python
from audit_orchestrator.config import Settings

settings = Settings.from_args()

# Configurar concurrencia
settings.max_concurrent_targets = 15

# Configurar auto-review
settings.auto_review_on_run = True

# Configurar threshold de errores (80%)
settings.review_error_threshold = 0.8
```

### Variables de Entorno

```bash
# .env
AUDIT_MAX_CONCURRENT=15
AUDIT_AUTO_REVIEW=true
AUDIT_ERROR_THRESHOLD=0.8
KALI_SERVER_URL=http://kali-server:5001
```

### Ajuste Según Infraestructura

| Escenario | max_concurrent | Notas |
|-----------|----------------|-------|
| Laptop local | 5-10 | Recursos limitados |
| Workstation potente | 15-25 | CPU/RAM abundantes |
| Servidor dedicado | 30-50 | Máxima paralelización |
| Kali MCP lento | 3-5 | Limitar para no saturar |
| Red lenta | 5-10 | Reducir carga de red |

---

## Troubleshooting

### Problema: Auditorías fallan con concurrencia alta

**Síntoma:** Muchos targets fallan cuando `max_concurrent > 15`

**Causa:** Servidor Kali MCP saturado o límites de red

**Solución:**
1. Reducir `max_concurrent` a 5-10
2. Verificar recursos del servidor Kali
3. Ejecutar `audit_review` para re-encolar fallidos
4. Re-intentar con menor concurrencia

### Problema: Auto-review no detecta fallos

**Síntoma:** Targets claramente fallidos no se re-encolan

**Causa:** Error threshold muy alto o bitacora incorrecta

**Solución:**
1. Reducir `review_error_threshold` a 0.6 (60%)
2. Verificar manualmente bitacora: `cat /tmp/audit/10.1.1.50/bitacora/*.log`
3. Ejecutar `audit_review` con `re_enqueue_failed=true`

### Problema: Ejecución paralela más lenta que secuencial

**Síntoma:** Duración mayor en paralelo que en secuencial

**Causa:** Overhead de coordinación o recursos limitados

**Solución:**
1. Verificar que `max_concurrent` no sea demasiado bajo (< 5)
2. Aumentar concurrencia gradualmente
3. Verificar que Kali MCP soporte múltiples requests

### Problema: Bitacora vacía pero auditoría "completed"

**Síntoma:** Target marcado como "completed" pero sin outputs

**Causa:** Error silencioso en ejecución de comandos

**Solución:**
1. Ejecutar `audit_review` para detectar y re-encolar
2. Verificar logs del servidor Kali
3. Re-ejecutar en modo secuencial para debugging: `parallel=false`

### Problema: SERVICES_REPORT.md no se genera

**Síntoma:** No aparece el archivo después de review

**Causa:** Error en generación de reporte

**Solución:**
1. Ejecutar manualmente: `audit_review(project_id, re_enqueue_failed=true)`
2. Verificar permisos en directorio del proyecto
3. Revisar logs de error

---

## Métricas de Rendimiento

### Benchmark: 100 Targets

| Configuración | Duración | Throughput | Notas |
|---------------|----------|------------|-------|
| Sequential | ~1200s (20min) | 0.08 targets/s | Legacy |
| Parallel (5) | ~300s (5min) | 0.33 targets/s | 4x faster |
| Parallel (10) | ~150s (2.5min) | 0.67 targets/s | 8x faster |
| Parallel (20) | ~90s (1.5min) | 1.11 targets/s | 13x faster |
| Parallel (50) | ~60s (1min) | 1.67 targets/s | 20x faster* |

\* *Resultados pueden variar según hardware y red*

### Recomendaciones

- **Inicio conservador:** Empezar con `max_concurrent=5-10`
- **Escalar gradualmente:** Aumentar si la infraestructura lo permite
- **Monitorear recursos:** CPU, RAM, y red del servidor Kali
- **Auto-review siempre ON:** Detecta y corrige fallos automáticamente

---

## Recursos Adicionales

- [Arquitectura del Sistema](ARQUITECTURA.md)
- [Guía de Uso Rápido](USO_RAPIDO.md)
- [README Principal](../README.md)
- [CHANGELOG](CHANGELOG.md)

---

**Versión:** 0.3.0  
**Última actualización:** Octubre 2024
