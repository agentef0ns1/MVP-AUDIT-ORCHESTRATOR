# Instalación y Configuración

## Requisitos Previos

### Sistema
- Linux (probado en Debian/Ubuntu/Kali)
- Python 3.10 o superior
- SQLite 3

### Kali MCP Server
Debe estar corriendo en `http://127.0.0.1:5001`

Ver documentación del Kali MCP Server para su instalación.

## Instalación

### 1. Clonar/Ubicar el Repositorio

```bash
cd /opt/cline-mcps/
# Si no existe, clonar o copiar el proyecto aquí
```

### 2. Instalar Dependencias

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator

# Instalar en modo desarrollo
pip install -e .
```

### 3. Configurar MCP en Cursor

Editar `~/.cursor/mcp_servers.json` (o crear si no existe):

```json
{
  "mcpServers": {
    "audit-orchestrator": {
      "command": "python3",
      "args": [
        "-m",
        "audit_orchestrator.mcp_server",
        "--transport",
        "stdio"
      ],
      "cwd": "/opt/cline-mcps/MVP-audit-orchestrator"
    }
  }
}
```

### 4. Reiniciar Cursor

1. Cierra Cursor completamente
2. Reabre Cursor
3. Ve a Settings → MCP Servers
4. Verifica que "audit-orchestrator" esté activo (verde)

## Verificación

### Test de Conexión

Desde Cursor chat:

```python
audit_status()
```

Debe retornar información sobre proyectos (o lista vacía si no hay proyectos aún).

### Test Completo

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
python3 dev-tools/verify_installation.py
```

Debe mostrar:
```
✅ Core modules import OK
✅ Database schema v2 OK
✅ All MCP tools available
✅ Command validator OK
✅ SSL detection working
✅ All checks passed
```

## Configuración Opcional

### Ubicación de Base de Datos

Por defecto: `~/.local/share/audit-orchestrator/audit_state.db`

Para cambiar:

```json
{
  "mcpServers": {
    "audit-orchestrator": {
      "command": "python3",
      "args": [
        "-m",
        "audit_orchestrator.mcp_server",
        "--data-dir",
        "/ruta/custom",
        "--transport",
        "stdio"
      ]
    }
  }
}
```

### URL de Kali Server

Por defecto: `http://127.0.0.1:5001`

Para cambiar:

```json
{
  "args": [
    "-m",
    "audit_orchestrator.mcp_server",
    "--kali-server-url",
    "http://otra-ip:puerto",
    "--transport",
    "stdio"
  ]
}
```

## Actualización

### Desde v1.0 a v2.0

La migración de base de datos es **automática** al iniciar el servidor.

Si hay problemas:

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
python3 dev-tools/migrate_database.py
```

Luego reinicia el servidor MCP en Cursor.

### Pull de Cambios

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
git pull origin main
pip install -e . --force-reinstall
```

Reinicia Cursor después.

## Desinstalación

### Eliminar Configuración MCP

Editar `~/.cursor/mcp_servers.json` y eliminar la sección `audit-orchestrator`.

### Eliminar Base de Datos

```bash
rm -rf ~/.local/share/audit-orchestrator/
```

### Desinstalar Paquete Python

```bash
pip uninstall audit-orchestrator
```

## Troubleshooting

### Error: "Connection closed" o "-32000"

**Causa**: Base de datos necesita migración

**Solución**:
```bash
python3 dev-tools/migrate_database.py
```

Luego reinicia el servidor en Cursor (Settings → MCP Servers → Restart).

### Error: "Module not found"

**Causa**: Instalación incompleta

**Solución**:
```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
pip install -e . --force-reinstall
```

### Servidor no aparece en Cursor

**Causa**: Configuración incorrecta o Cursor no reiniciado

**Verificar**:
1. `~/.cursor/mcp_servers.json` tiene configuración correcta
2. La ruta `cwd` existe
3. Python 3.10+ instalado
4. Cursor completamente cerrado y reabierto

### SSL services usan HTTP en vez de HTTPS

**Causa**: Versión antigua del código

**Verificar**:
```bash
python3 dev-tools/test_ssl_detection.py
```

Debe mostrar: `✅ ssl/radan-http → https`

Si falla:
```bash
git pull origin main
pip install -e . --force-reinstall
```

### "attempt to write a readonly database"

**Causa**: Permisos

**Solución**:
```bash
chmod 644 ~/.local/share/audit-orchestrator/audit_state.db
chmod 755 ~/.local/share/audit-orchestrator/
```

### Kali Server no responde

**Verificar**:
```bash
curl http://127.0.0.1:5001/health
```

Debe retornar JSON con status OK.

Si falla, verificar que el Kali MCP Server esté corriendo.

### Timeout en comandos largos

**Causa**: Timeout por defecto (15 min por servicio)

**Cambiar** (solo si es necesario):
Editar `src/audit_orchestrator/config.py`:
```python
max_time_per_service: int = 1800  # 30 minutos
```

## Logs y Debug

### Ver Logs del Servidor MCP

Cursor muestra logs en Developer Tools:

1. Cursor → Help → Toggle Developer Tools
2. Tab "Console"
3. Buscar logs de "audit-orchestrator"

### Ejecutar Servidor Manualmente (Debug)

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
python3 -m audit_orchestrator.mcp_server --transport stdio
```

Espera input en stdin, escribe comandos y observa errores en stderr.

### Logs de Base de Datos

```bash
sqlite3 ~/.local/share/audit-orchestrator/audit_state.db

# Ver proyectos
SELECT * FROM projects;

# Ver bitacora
SELECT * FROM bitacora_entries ORDER BY timestamp DESC LIMIT 20;

# Ver schema version
SELECT * FROM schema_version;
```

## Performance

### Base de Datos

SQLite es suficiente para la mayoría de casos. Para proyectos muy grandes (100+ targets):

1. Usar SSD para `~/.local/share/audit-orchestrator/`
2. Considerar aumentar `cache_size` de SQLite
3. Limpiar proyectos antiguos periódicamente

### Paralelización

Actualmente los targets se procesan **secuencialmente**. Para acelerar:

1. Ejecutar múltiples proyectos en paralelo (diferentes `base_path`)
2. Usar múltiples instancias de Kali MCP Server
3. Futura feature: procesamiento paralelo interno

## Seguridad

### Aislamiento

El orquestador ejecuta comandos en el Kali MCP Server, **NO localmente**.

Asegúrate de que el Kali Server esté en:
- Red aislada/controlada
- Sin acceso a sistemas críticos
- Con límites de recursos (CPU, RAM, network)

### Validación de Comandos

Type 2 y Type 3 validan todos los comandos antes de ejecutar.

Ver lista completa en `src/audit_orchestrator/core/command_validator.py`.

### Limits Type 3

No modificables desde el exterior:
- 50 comandos por target
- 30 minutos por target

Para cambiar, editar `src/audit_orchestrator/core/orchestrator.py`:
```python
MAX_COMMANDS = 50
MAX_TIME_SECONDS = 1800
```

## Soporte

### Documentación
- `docs/ARQUITECTURA.md` - Arquitectura del sistema
- `docs/USO_RAPIDO.md` - Guía rápida de uso
- `docs/LLM_EXECUTION_MODES.md` - Detalles de modos LLM

### Scripts Útiles
- `dev-tools/verify_installation.py` - Verificación completa
- `dev-tools/migrate_database.py` - Migración manual
- `scripts/list_all_projects.py` - Listar proyectos
- `scripts/check_project_status.py` - Estado de proyecto

---

**Versión**: 2.0.0  
**Última actualización**: 2026-10-01
