# Inicio rápido — comandos MCP para el agente Cline

Estas son las invocaciones actuales del servidor MCP `audit-orchestrator`. El agente las llama tal cual. El workspace es `base_path` y el nmap de entrada es `input_file` (por defecto `open_ports.txt`). El perfil por defecto es `default_blackbox`.

`parallel=true` lanza varios hosts a la vez. `max_concurrent` es el tope de hilos simultáneos (por defecto `10`).

---

## Ejemplo tipo 1 — `type_1_no_llm`

Ejecuta la secuencia fija del perfil, sin LLM. Sirve para una pasada automática y predecible.

```text
audit_start_and_run(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC",
    input_file="open_ports.txt",
    profile="default_blackbox",
    execution_mode="type_1_no_llm",
    reset=false,
    parallel=true,
    max_concurrent=10
)
```

Al acabar, generar el resumen:

```text
audit_finalize(project_id="<project_id>")
```

---

## Ejemplo tipo 2 — `type_2_post_host_llm`

Enumera el host con el perfil y después entrega el resultado al agente. El agente lee un servicio cada vez y, si hace falta, ejecuta una sola comprobación segura. Sin DoS, sin fuerza bruta y sin explotación.

```text
audit_start_and_run(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC",
    input_file="open_ports.txt",
    profile="default_blackbox",
    execution_mode="type_2_post_host_llm",
    reset=false,
    parallel=true,
    max_concurrent=10
)
```

Con el primer elemento de `pending_llm`, pedir el índice:

```text
audit_llm_analyze_host(
    project_id="<project_id>",
    target_id="<target_id>"
)
```

Leer un puerto concreto:

```text
audit_llm_analyze_host(
    project_id="<project_id>",
    target_id="<target_id>",
    port=443
)
```

Una comprobación segura, o ninguna:

```text
audit_llm_execute_poc(
    project_id="<project_id>",
    target_id="<target_id>",
    command="curl -skI https://10.19.220.23/",
    reason="Comprobar cabeceras del servicio HTTPS ya enumerado en el puerto 443"
)
```

Registrar solo un hallazgo observado en la salida:

```text
audit_record_finding(
    project_id="<project_id>",
    target="10.19.220.23",
    severity="medium",
    title="Título del hallazgo",
    description="Qué se observó en la salida de la enumeración",
    port=443,
    service="https",
    evidence="Extracto de la salida"
)
```

Seguir con el siguiente `port` y, al terminar el host, con el siguiente `pending_llm`.

---

## Ejemplo tipo 3 — `type_3_interactive_llm`

El perfil se detiene al terminar cada puerto. El agente lee ese puerto, puede anotar un hallazgo o lanzar un comando extra sobre el mismo puerto, y pide el siguiente. Tope: 50 comandos o 30 minutos por host.

```text
audit_start_and_run(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC",
    input_file="open_ports.txt",
    profile="default_blackbox",
    execution_mode="type_3_interactive_llm",
    reset=false,
    parallel=true,
    max_concurrent=10
)
```

Releer el puerto en curso:

```text
audit_llm_get_context(
    project_id="<project_id>",
    target_id="<target_id>"
)
```

Profundizar solo en ese puerto:

```text
audit_llm_next_command(
    project_id="<project_id>",
    target_id="<target_id>",
    command="whatweb -a 1 https://10.19.220.23:443",
    reason="El puerto 443 respondió HTTPS y falta identificar la tecnología"
)
```

Pasar al puerto siguiente:

```text
audit_llm_continue(
    project_id="<project_id>",
    target_id="<target_id>"
)
```

Cuando `audit_llm_continue` devuelve `done=true`, cerrar con `audit_finalize(project_id)`.

---

## Paralelo multithread y `max_concurrent`

Varios hosts corren a la vez. `max_concurrent` fija cuántos hilos (hosts) pueden estar activos. El defecto es `10`.

Veinte hosts simultáneos desde el arranque:

```text
audit_start_and_run(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC",
    input_file="open_ports.txt",
    profile="default_blackbox",
    execution_mode="type_1_no_llm",
    reset=false,
    parallel=true,
    max_concurrent=20
)
```

El mismo tope si el proyecto ya existe:

```text
audit_run(
    project_id="<project_id>",
    parallel=true,
    max_concurrent=20
)
```

Reanudar lo pendiente o interrumpido. `audit_resume` siempre ejecuta en paralelo:

```text
audit_resume(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC",
    input_file="open_ports.txt",
    max_concurrent=20
)
```

Un solo host cada vez:

```text
audit_run(
    project_id="<project_id>",
    parallel=false
)
```

---

## Estado de una auditoría

Estado por identificador. La respuesta incluye `status`, `profile`, `statistics` (targets, servicios y hallazgos por severidad), `last_operation`, `next_target` y `done`.

```text
audit_status(project_id="<project_id>")
```

Estado por directorio. Usar el mismo `input_file` con el que se creó el proyecto.

```text
audit_status_by_path(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC",
    input_file="open_ports.txt"
)
```

Listar auditorías. `status` puede ser `running`, `completed` o `paused`.

```text
audit_list_projects(status="running", limit=50)
```

Hosts y su estado (`pending`, `auditing`, `completed`, `failed`, `pending_llm_analysis`):

```text
audit_get_targets(
    project_id="<project_id>",
    status="pending"
)
```

Hallazgos, con filtro opcional de severidad (`critical`, `high`, `medium`, `low`, `info`):

```text
audit_get_findings(
    project_id="<project_id>",
    severity="high"
)
```

Bitácora de un host:

```text
audit_get_bitacora(
    project_id="<project_id>",
    target="10.19.220.23",
    limit=20
)
```

Resumen ejecutivo en `RESUMEN-AUDITORIA.md`:

```text
audit_finalize(project_id="<project_id>")
```

`done=true` significa que no queda ningún host pendiente.
