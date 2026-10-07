# Quick Start — comandos MCP para el agente Cline

Servidor MCP: `audit-orchestrator` (este repositorio).
El agente invoca estas herramientas. El fichero de entrada es un nmap (`-oN`, `-oG`, `-oX` o varios hosts concatenados) dentro de `base_path`. Por defecto se llama `open_ports.txt`. El perfil por defecto es `default_blackbox`.

`parallel=true` ejecuta varios hosts a la vez. `max_concurrent` es el tope de hilos (hosts simultáneos). Por defecto vale `10`.

Al terminar una auditoría, llamar `audit_finalize(project_id)`.

---

## Ejemplo tipo 1 — `type_1_no_llm`

Secuencia fija del perfil JSON. No interviene el LLM. Es el modo para una auditoría automática y repetible.

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

Cuando la respuesta traiga `status=completed` y `done` implícito (sin `pending_llm`):

```text
audit_finalize(project_id="<project_id>")
```

---

## Ejemplo tipo 2 — `type_2_post_host_llm`

El perfil enumera cada host. Después el agente analiza los resultados y puede lanzar como máximo una prueba segura por puerto. Sin DoS, sin fuerza bruta y sin explotación.

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

Si la respuesta trae `pending_llm`, seguir con el primer host (`pending_llm[0]`):

```text
audit_llm_analyze_host(
    project_id="<project_id>",
    target_id="<target_id>"
)
```

Esa llamada devuelve el índice de servicios. Repetirla con `port` para leer un servicio:

```text
audit_llm_analyze_host(
    project_id="<project_id>",
    target_id="<target_id>",
    port=443
)
```

Como máximo un comando seguro para ese puerto, o ninguno:

```text
audit_llm_execute_poc(
    project_id="<project_id>",
    target_id="<target_id>",
    command="curl -skI https://10.19.220.23/",
    reason="Comprobar cabeceras del servicio HTTPS ya enumerado en el puerto 443"
)
```

Un hallazgo real se registra con:

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

Pasar al siguiente puerto del índice hasta agotar los servicios del host, y luego al siguiente elemento de `pending_llm`.

---

## Ejemplo tipo 3 — `type_3_interactive_llm`

Solo corre el arranque del perfil y se detiene en cada puerto. El agente lee el prompt de ese puerto, puede registrar un hallazgo o profundizar con un comando, y después pide el puerto siguiente. Límite: 50 comandos o 30 minutos por host.

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

La respuesta trae `prompt`, `step` y `continue_with`. Para releer el puerto que acaba de terminar:

```text
audit_llm_get_context(
    project_id="<project_id>",
    target_id="<target_id>"
)
```

Para repetir o profundizar solo ese puerto:

```text
audit_llm_next_command(
    project_id="<project_id>",
    target_id="<target_id>",
    command="whatweb -a 1 https://10.19.220.23:443",
    reason="El puerto 443 respondió HTTPS y falta identificar la tecnología"
)
```

Cuando ese puerto no necesita nada más, el siguiente puerto se lanza con:

```text
audit_llm_continue(
    project_id="<project_id>",
    target_id="<target_id>"
)
```

Repetir hasta que `audit_llm_continue` devuelva `done=true`. Entonces `audit_finalize(project_id)`.

---

## Paralelo multithread y `max_concurrent`

`parallel=true` audita varios hosts a la vez. `max_concurrent` es el número máximo de hilos (hosts simultáneos). El valor por defecto es `10`. Subirlo acelera la auditoría y carga más el servidor Kali.

Arranque con 20 hosts a la vez:

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

El mismo tope sobre un proyecto ya creado:

```text
audit_run(
    project_id="<project_id>",
    parallel=true,
    max_concurrent=20
)
```

Reanudar hosts pendientes o interrumpidos, también en paralelo. Esta llamada siempre corre en paralelo:

```text
audit_resume(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC",
    input_file="open_ports.txt",
    max_concurrent=20
)
```

Un hilo cada vez (depuración):

```text
audit_run(
    project_id="<project_id>",
    parallel=false
)
```

---

## Estado de una auditoría

Por `project_id`. Devuelve `status`, `profile`, `statistics` (targets, servicios y hallazgos), `last_operation`, `next_target` y `done`.

```text
audit_status(project_id="<project_id>")
```

Por directorio, sin recordar el UUID. `input_file` tiene que ser el mismo con el que se creó el proyecto.

```text
audit_status_by_path(
    base_path="/home/f0ns1/RedTeam/OCSR25/PoC",
    input_file="open_ports.txt"
)
```

Listar proyectos. `status` admite `running`, `completed` o `paused`.

```text
audit_list_projects(status="running", limit=50)
```

Hosts del proyecto. `status` opcional: `pending`, `auditing`, `completed`, `failed`, `pending_llm_analysis`.

```text
audit_get_targets(
    project_id="<project_id>",
    status="pending"
)
```

Hallazgos. `severity` opcional: `critical`, `high`, `medium`, `low`, `info`.

```text
audit_get_findings(
    project_id="<project_id>",
    severity="high"
)
```

Bitácora. `target` y `limit` son opcionales.

```text
audit_get_bitacora(
    project_id="<project_id>",
    target="10.19.220.23",
    limit=20
)
```

Cerrar y generar `RESUMEN-AUDITORIA.md`:

```text
audit_finalize(project_id="<project_id>")
```

`done=true` en `audit_status` indica que no queda ningún host pendiente.
