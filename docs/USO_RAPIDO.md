# Uso Rápido

## Inicio Rápido

### Método Simple (Recomendado)

**Un solo comando, sin manejar UUIDs**:

```python
# Todo en uno: start + run
audit_start_and_run(
    base_path="/tmp/mi_auditoria",
    input_file="open_ports.txt"
)
```

Resultados aparecen en `/tmp/mi_auditoria/`.

### Método Tradicional (con project_id)

Si necesitas más control:

#### 1. Preparar Input

```bash
# Escaneo directo
nmap -sV -p- 10.19.220.0/24 -oN open_ports.txt
```

#### 2. Iniciar Auditoría

```python
audit_start(
    base_path="/tmp/mi_auditoria",
    input_file="open_ports.txt"
)
```

Respuesta:
```json
{
  "project_id": "abc-123-def-456",
  "targets_count": 5,
  "services_count": 23
}
```

#### 3. Ejecutar Auditoría

```python
audit_run(project_id="abc-123-def-456")
```

#### 4. Ver Resultados

```python
# Ver hallazgos
audit_get_findings(project_id="abc-123-def-456")

# Ver estado
audit_status(project_id="abc-123-def-456")
```

### Continuar/Resumir Auditoría

**Sin necesitar el project_id**:

```python
# Continuar desde donde se quedó
audit_resume(base_path="/tmp/mi_auditoria")

# Ver estado sin project_id
audit_status_by_path(base_path="/tmp/mi_auditoria")
```

### 5. Resultados en Filesystem

```bash
/tmp/mi_auditoria/
├── open_ports.txt           # Input original
├── 10.19.220.23/            # Target 1
│   ├── 80_tcp_http/         # Puerto 80
│   │   ├── whatweb.txt
│   │   ├── nikto.txt
│   │   └── ffuf.txt
│   ├── 443_tcp_ssl_http/    # Puerto 443 (SSL)
│   │   ├── sslscan.txt
│   │   ├── whatweb.txt
│   │   └── ffuf.txt
│   └── bitacora.txt         # Log del target
├── 10.19.220.24/            # Target 2
│   └── ...
└── resumen_auditoria.txt    # Resumen general
```

## Comandos Sin project_id (Nuevos)

### Inicio y Ejecución en Un Paso

```python
# Todo automático: start + run
audit_start_and_run(
    base_path="/tmp/audit",
    input_file="open_ports.txt",
    execution_mode="type_1_no_llm"  # o type_2, type_3
)
```

**Ventajas**:
- ✅ No necesitas copiar/pegar el project_id
- ✅ Un solo comando
- ✅ Ideal para modelos LLM (menos pasos)

### Continuar Auditoría Existente

```python
# Continuar desde directorio (sin project_id)
audit_resume(base_path="/tmp/audit")
```

Útil cuando:
- La auditoría fue interrumpida
- Quieres procesar más targets
- Necesitas re-ejecutar sin buscar el UUID

### Ver Estado por Directorio

```python
# Estado sin project_id
audit_status_by_path(base_path="/tmp/audit")
```

Devuelve lo mismo que `audit_status()` pero sin necesitar UUID.

## Comandos Comunes

### Listar Proyectos

```python
audit_list_projects()
```

### Estado de Proyecto

```python
audit_status(project_id="abc-123")
```

Respuesta:
```json
{
  "project_id": "abc-123",
  "status": "running",  // o "completed"
  "targets": 5,
  "targets_completed": 3,
  "services_audited": 18,
  "findings": 12
}
```

### Ver Bitácora

```python
audit_get_bitacora(project_id="abc-123")
```

### Obtener Targets

```python
audit_get_targets(project_id="abc-123")
```

### Ver Hallazgos por Severidad

```python
findings = audit_get_findings(project_id="abc-123")
# findings["findings"] contiene lista con severity: critical, high, medium, low, info
```

## Tres Modos de Ejecución

### Modo 1: Sin LLM (Default)

```python
audit_start(
    base_path="/tmp/audit",
    input_file="open_ports.txt",
    execution_mode="type_1_no_llm"  # Default, se puede omitir
)
```

**Características**:
- Rápido y predecible
- Secuencia fija del JSON profile
- No requiere LLM

**Cuándo usar**: Auditorías estándar, CI/CD, cuando speed es prioridad.

### Modo 2: LLM Post-Host

```python
audit_start(
    base_path="/tmp/audit",
    input_file="open_ports.txt",
    execution_mode="type_2_post_host_llm"
)
```

**Características**:
- Ejecuta todas las tareas del JSON primero
- Después analiza resultados con LLM
- LLM propone y ejecuta PoCs automáticamente

**Cuándo usar**: Auditorías exhaustivas, cuando necesitas verificación inteligente.

**Flujo LLM** (automático o manual):
```python
# Después de audit_run(), el LLM puede:

# 1. Obtener contexto del host
context = audit_llm_analyze_host(
    project_id="abc-123",
    target_id="target-456"
)

# 2. Ejecutar PoCs basados en análisis
audit_llm_execute_poc(
    project_id="abc-123",
    target_id="target-456",
    command="curl -k https://10.19.220.23/admin",
    reason="Verificar acceso no autenticado a panel admin detectado en nikto"
)
```

### Modo 3: LLM Control Total

```python
audit_start(
    base_path="/tmp/audit",
    input_file="open_ports.txt",
    execution_mode="type_3_interactive_llm"
)
```

**Características**:
- Solo ejecuta nmap -sV inicial
- LLM decide cada comando subsecuente
- Límites: 50 comandos o 30 minutos por target

**Cuándo usar**: Targets complejos, investigación, máxima adaptabilidad.

**Flujo LLM** (loop):
```python
# Después de audit_run():

# 1. Obtener contexto actual
context = audit_llm_get_context(
    project_id="abc-123",
    target_id="target-456"
)

# 2. LLM decide siguiente comando
result = audit_llm_next_command(
    project_id="abc-123",
    target_id="target-456",
    command="whatweb http://10.19.220.23:8088",
    reason="Nmap detectó HTTP en 8088, identificando tecnologías web"
)

# 3. Verificar límites
print(result["limits_status"])
# {"commands_remaining": 49, "time_remaining": 1795}

# 4. Repetir hasta límite o completar objetivo
```

## Reset y Limpieza

### Reset de Proyecto (mantener estructura)

```python
audit_reset_project(project_id="abc-123")
```

Esto:
- ✅ Marca targets como "pending"
- ✅ Marca servicios como "pending"
- ✅ Mantiene estructura de directorios
- ✅ Mantiene proyecto en DB
- ❌ NO borra outputs de comandos

Para re-ejecutar:
```python
audit_run(project_id="abc-123")
```

### Eliminar Proyecto Completamente

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
python3 scripts/delete_project_completely.py abc-123
```

Esto borra:
- ✅ Proyecto de DB
- ✅ Todos los targets, servicios, tareas
- ✅ Todos los findings y bitácora
- ✅ Directorio completo del proyecto

### Reset Completo de Base de Datos

```bash
python3 scripts/reset_database_completely.py
```

⚠️ **CUIDADO**: Esto borra **TODOS** los proyectos.

### Limpiar Proyectos Antiguos

```bash
# Listar todos los proyectos
python3 scripts/list_all_projects.py

# Eliminar los que no necesites
python3 scripts/delete_project_completely.py <project_id>
```

## Casos de Uso Comunes

### Caso 1: Auditoría Rápida (5 minutos)

```python
# 1. Preparar
# Tener open_ports.txt con 1-2 targets

# 2. Iniciar
audit_start(base_path="/tmp/quick_audit", input_file="open_ports.txt")

# 3. Ejecutar
audit_run(project_id="...")

# 4. Ver resultados mientras corre
audit_status(project_id="...")
```

### Caso 2: Auditoría Completa de Red (horas)

```python
# 1. Escaneo previo
nmap -sV -p- 10.19.220.0/24 -oN subnet_scan.txt

# 2. Iniciar con modo LLM post-host
audit_start(
    base_path="/var/audits/subnet_220",
    input_file="subnet_scan.txt",
    execution_mode="type_2_post_host_llm"
)

# 3. Ejecutar (puede tomar horas)
audit_run(project_id="...")

# 4. El LLM analizará cada host automáticamente
# Ver progreso:
audit_status(project_id="...")
```

### Caso 3: Investigación de Target Específico

```python
# 1. Crear input con 1 solo target
echo "10.19.220.25" > single_target.txt
echo "80/tcp open http nginx" >> single_target.txt
echo "443/tcp open ssl/http nginx" >> single_target.txt

# 2. Modo 3 para investigación interactiva
audit_start(
    base_path="/tmp/investigation",
    input_file="single_target.txt",
    execution_mode="type_3_interactive_llm"
)

# 3. Ejecutar bootstrap
audit_run(project_id="...")

# 4. LLM toma control total y explora adaptativamente
```

### Caso 4: Re-auditar Después de Cambios

```python
# 1. Ya tienes un proyecto
project_id = "abc-123"

# 2. Reset (mantiene estructura)
audit_reset_project(project_id=project_id)

# 3. Re-ejecutar
audit_run(project_id=project_id)

# Compara resultados nuevos con anteriores en directorios
```

## Tips y Trucos

### Ver Log en Tiempo Real

```bash
# En terminal separada
tail -f /tmp/mi_auditoria/*/bitacora.txt
```

### Buscar Finding Específico

```python
findings = audit_get_findings(project_id="abc-123")
for f in findings["findings"]:
    if "SQL" in f["title"]:
        print(f"{f['target']}: {f['title']} - {f['severity']}")
```

### Auditar Solo Puertos Específicos

Editar `open_ports.txt` manualmente:
```
10.19.220.23
80/tcp open http
443/tcp open ssl/http
```

### Cambiar Timeout por Servicio

Editar `src/audit_orchestrator/config.py`:
```python
max_time_per_service: int = 900  # 15 minutos
```

O al crear proyecto (futuro):
```python
audit_start(..., max_time_per_service=1800)  # 30 min
```

### Ver Qué Comandos se Ejecutaron

```python
bitacora = audit_get_bitacora(project_id="abc-123")
for entry in bitacora["entries"]:
    if entry.get("command"):
        print(f"{entry['timestamp']}: {entry['command']}")
```

### Exportar Findings a JSON

```python
import json

findings = audit_get_findings(project_id="abc-123")
with open("findings.json", "w") as f:
    json.dump(findings, f, indent=2)
```

### Continuar Auditoría Interrumpida

```python
# Si audit_run() fue interrumpido:
# 1. Verificar estado
audit_status(project_id="abc-123")

# 2. Simplemente re-ejecutar
audit_run(project_id="abc-123")

# El sistema continuará desde donde se quedó
```

## Formatos de Input Soportados

### Formato 1: Nmap estándar

```
Nmap scan report for 10.19.220.23
Host is up.

PORT     STATE SERVICE     VERSION
80/tcp   open  http        nginx 1.18.0
443/tcp  open  ssl/http    nginx 1.18.0
8088/tcp open  ssl/radan-http myServer
```

### Formato 2: Simple

```
10.19.220.23
80/tcp open http
443/tcp open ssl/http
```

### Formato 3: Con discovered

```
10.19.220.23
Discovered open port 80/tcp on 10.19.220.23
80/tcp open http nginx
```

### Formato 4: JSON

```json
{
  "targets": [
    {
      "ip": "10.19.220.23",
      "ports": [
        {"port": 80, "protocol": "tcp", "service": "http"},
        {"port": 443, "protocol": "tcp", "service": "ssl/http"}
      ]
    }
  ]
}
```

## Detección Automática SSL/HTTPS

El sistema detecta automáticamente servicios SSL y usa HTTPS:

```
Entrada nmap:
  8088/tcp open ssl/radan-http myServer

Detección:
  ✅ "ssl" detectado → usa profile "https"

Comandos ejecutados:
  ✅ whatweb https://target:8088
  ✅ ffuf -u https://target:8088/FUZZ
  ✅ sslscan target:8088

NO ejecuta:
  ❌ whatweb http://target:8088
```

Servicios detectados como SSL/HTTPS:
- `ssl/http`, `ssl/radan-http`, `ssl/http-alt`
- `tls/http`, `tls/https`
- `https`

## Errores Comunes

### "Project not found"

**Causa**: project_id incorrecto

**Solución**:
```python
# Listar proyectos
audit_list_projects()
```

### "Target already completed"

**Causa**: Target ya fue auditado

**Solución**:
```python
# Reset y re-ejecutar
audit_reset_project(project_id="abc-123")
audit_run(project_id="abc-123")
```

### "Kali server not responding"

**Causa**: Kali MCP Server no disponible

**Verificar**:
```bash
curl http://127.0.0.1:5001/health
```

### "Command limit reached" (Type 3)

**Causa**: Alcanzaste 50 comandos

**Esto es normal**: Type 3 tiene límite de 50 comandos por target.

### "Time limit reached" (Type 3)

**Causa**: 30 minutos por target alcanzados

**Esto es normal**: Type 3 tiene límite de 30 minutos por target.

## Shortcuts para Cursor

Guardar estos snippets en Cursor:

```python
# Snippet 1: Quick audit
audit_start(base_path="/tmp/audit", input_file="open_ports.txt")
# Copiar project_id
audit_run(project_id="PROJECT_ID")
audit_get_findings(project_id="PROJECT_ID")

# Snippet 2: LLM mode
audit_start(base_path="/tmp/audit", input_file="open_ports.txt", execution_mode="type_2_post_host_llm")

# Snippet 3: Reset
audit_reset_project(project_id="PROJECT_ID")
audit_run(project_id="PROJECT_ID")

# Snippet 4: Clean
# En terminal:
python3 scripts/delete_project_completely.py PROJECT_ID
```

---

**Versión**: 2.0.0  
**Última actualización**: 2026-10-01
