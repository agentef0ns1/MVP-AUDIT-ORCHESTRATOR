# Ejemplos de Uso - Convenience Tools

## Workflow Simple (Recomendado)

### Caso 1: Auditoría Completa en Un Comando

```python
# Todo en uno: start + run
audit_start_and_run(
    base_path="/home/user/audits/client_xyz",
    input_file="open_ports.txt",
    execution_mode="type_1_no_llm"
)
```

**Respuesta**:
```json
{
  "success": true,
  "project_id": "a1b2c3d4-...",
  "base_path": "/home/user/audits/client_xyz",
  "execution_mode": "type_1_no_llm",
  "setup": {
    "targets_count": 15,
    "services_count": 87
  },
  "execution": {
    "targets_processed": 15,
    "targets_completed": 15,
    "services_audited": 87,
    "findings_created": 23
  },
  "status": "completed",
  "note": "Audit started and executed successfully. Results in: /home/user/audits/client_xyz"
}
```

### Caso 2: Continuar Auditoría Existente

```python
# Si la auditoría fue interrumpida o quieres procesar más targets
audit_resume(base_path="/home/user/audits/client_xyz")
```

**Cuándo usar**:
- Auditoría interrumpida por timeout
- Auditoría interrumpida manualmente
- Añadiste más targets al input file
- Quieres re-ejecutar targets fallidos

### Caso 3: Ver Estado Sin project_id

```python
# Consultar estado solo con directorio
audit_status_by_path(base_path="/home/user/audits/client_xyz")
```

**Respuesta**:
```json
{
  "project_id": "a1b2c3d4-...",
  "base_path": "/home/user/audits/client_xyz",
  "status": "completed",
  "targets": {
    "total": 15,
    "pending": 0,
    "in_progress": 0,
    "completed": 15,
    "failed": 0
  },
  "services": {
    "total": 87
  },
  "findings": {
    "total": 23,
    "by_severity": {
      "critical": 2,
      "high": 8,
      "medium": 10,
      "low": 3
    }
  },
  "last_operation": "Audit completed",
  "next_pending_target": null,
  "is_complete": true
}
```

---

## Comparación: Antes vs Ahora

### Antes (Workflow Tradicional)

```python
# Paso 1: Start
result = audit_start(
    base_path="/tmp/audit",
    input_file="open_ports.txt"
)

# Paso 2: Extraer project_id (el modelo tiene que hacer esto)
project_id = result["project_id"]  # ← puede fallar

# Paso 3: Run (con UUID copiado)
audit_run(project_id=project_id)

# Paso 4: Ver estado (con UUID)
audit_status(project_id=project_id)
```

**Problemas**:
- ❌ 3-4 pasos separados
- ❌ Modelo tiene que extraer y recordar UUID
- ❌ Errores de copy/paste
- ❌ Más tokens consumidos
- ❌ Más oportunidades de error

### Ahora (Convenience Tools)

```python
# Todo en uno
audit_start_and_run(
    base_path="/tmp/audit",
    input_file="open_ports.txt"
)

# Ver estado sin UUID
audit_status_by_path(base_path="/tmp/audit")

# Continuar sin UUID
audit_resume(base_path="/tmp/audit")
```

**Beneficios**:
- ✅ 1 comando vs 3-4
- ✅ Sin manejo de UUIDs
- ✅ Más intuitivo
- ✅ Menos errores
- ✅ Menos tokens
- ✅ Mejor UX para modelos LLM

---

## Ejemplos por Execution Mode

### Mode 1: Sin LLM (Rápido)

```python
audit_start_and_run(
    base_path="/tmp/quick_scan",
    input_file="open_ports.txt",
    execution_mode="type_1_no_llm"
)
```

**Duración**: ~2-5 minutos para 10-15 hosts
**Uso**: Scans rápidos, reconocimiento inicial

### Mode 2: LLM Post-Host

```python
audit_start_and_run(
    base_path="/tmp/smart_scan",
    input_file="open_ports.txt",
    execution_mode="type_2_post_host_llm"
)
```

**Duración**: ~10-20 minutos para 10-15 hosts
**Uso**: Análisis automatizado después de cada host

### Mode 3: LLM Interactivo

```python
audit_start_and_run(
    base_path="/tmp/interactive_scan",
    input_file="open_ports.txt",
    execution_mode="type_3_interactive_llm",
    max_targets=3  # Limita targets por tiempo
)
```

**Duración**: ~30 minutos por target (límite)
**Uso**: Pentesting profundo y manual

---

## Escenarios Comunes

### Auditoría Diaria Automatizada

```bash
# Cron job que ejecuta auditoría todas las noches
0 2 * * * /opt/cline-mcps/MVP-audit-orchestrator/scripts/daily_audit.sh
```

```bash
#!/bin/bash
# daily_audit.sh

# Actualizar targets
nmap -sV -p- 10.0.0.0/24 > /audits/daily/open_ports.txt

# Ejecutar auditoría (desde Python/MCP)
# audit_start_and_run(
#   base_path="/audits/daily",
#   execution_mode="type_1_no_llm",
#   reset=True
# )
```

### Auditoría de Cliente (Manual)

```python
# 1. Preparar directorio
# mkdir -p /audits/client_abc
# cd /audits/client_abc
# nmap -sV -p- client.com > open_ports.txt

# 2. Ejecutar auditoría completa
audit_start_and_run(
    base_path="/audits/client_abc",
    execution_mode="type_2_post_host_llm"
)

# 3. Revisar resultados
audit_status_by_path(base_path="/audits/client_abc")

# 4. Si necesitas más análisis
audit_resume(
    base_path="/audits/client_abc",
    max_targets=5  # Solo 5 más
)
```

### Debugging/Testing

```python
# Reset completo
audit_reset_project(project_id="...")

# O eliminar y recrear
import os
os.system("python3 /opt/cline-mcps/MVP-audit-orchestrator/scripts/delete_project_completely.py abc-123")

# Volver a ejecutar
audit_start_and_run(
    base_path="/tmp/test",
    reset=True
)
```

---

## Tips & Tricks

### Tip 1: Limitar Tiempo/Targets

```python
# Procesar solo 5 targets (útil para testing)
audit_start_and_run(
    base_path="/tmp/test",
    max_targets=5
)
```

### Tip 2: Reset Automático

```python
# Reset workspace si ya existe
audit_start_and_run(
    base_path="/tmp/audit",
    reset=True  # ← borra datos previos
)
```

### Tip 3: Continuar Desde Fallo

```python
# Si algo falló a medias
audit_resume(base_path="/tmp/audit")

# Los targets completados se saltean
# Solo procesa pending/failed
```

### Tip 4: Cambiar Execution Mode

```python
# Primero rápido (Type 1)
audit_start_and_run(
    base_path="/tmp/audit",
    execution_mode="type_1_no_llm"
)

# Luego análisis profundo (Type 2)
# NO soportado - necesitas nuevo proyecto
# Solución: usar diferentes directorios
audit_start_and_run(
    base_path="/tmp/audit_deep",
    input_file="../audit/open_ports.txt",  # reusar input
    execution_mode="type_2_post_host_llm"
)
```

---

## Referencia Rápida

| Comando | Params Principales | Uso |
|---------|-------------------|-----|
| `audit_start_and_run()` | `base_path`, `execution_mode` | Iniciar y ejecutar en 1 paso |
| `audit_resume()` | `base_path` | Continuar auditoría existente |
| `audit_status_by_path()` | `base_path` | Ver estado sin project_id |

**Parámetros comunes**:
- `base_path`: Directorio del proyecto (requerido)
- `input_file`: Archivo nmap (default: `open_ports.txt`)
- `execution_mode`: `type_1_no_llm`, `type_2_post_host_llm`, `type_3_interactive_llm`
- `max_targets`: Límite de targets a procesar (opcional)
- `reset`: Borrar workspace existente (opcional, default: `False`)

---

**Documentación completa**:
- [docs/USO_RAPIDO.md](../docs/USO_RAPIDO.md)
- [docs/ARQUITECTURA.md](../docs/ARQUITECTURA.md)
- [README.md](../README.md)
