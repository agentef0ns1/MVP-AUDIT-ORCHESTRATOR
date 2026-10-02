# Dev Tools - Scripts de Desarrollo y Testing

Este directorio contiene herramientas para desarrollo, testing y troubleshooting.

**No son necesarios para uso normal del sistema.**

## Scripts de Verificación

### `verify_installation.py`
Verifica que toda la instalación esté correcta.

```bash
python3 verify_installation.py
```

Verifica:
- ✅ Imports de módulos
- ✅ Schema de base de datos
- ✅ MCP tools disponibles
- ✅ Command validator
- ✅ Detección SSL

### `migrate_database.py`
Migra manualmente la base de datos a v2.

```bash
python3 migrate_database.py
```

Usa esto si:
- Error "Connection closed" en MCP
- Error "duplicate column"
- Necesitas forzar migración

## Scripts de Testing

### `test_ssl_detection.py`
Prueba detección de servicios SSL/HTTPS.

```bash
python3 test_ssl_detection.py
```

Verifica que:
- `ssl/radan-http` → HTTPS ✅
- `ssl/http` → HTTPS ✅
- `tls/http` → HTTPS ✅

### `test_nmap_parser_ssl.py`
Prueba parser de nmap con servicios SSL.

```bash
python3 test_nmap_parser_ssl.py
```

### `test_nmap_formats.py`
Prueba parser con múltiples formatos de nmap.

```bash
python3 test_nmap_formats.py
```

Formatos:
- Nmap scan report for X
- PORT/tcp open service
- Discovered open port
- JSON estructurado

### `test_execution_modes.py`
Prueba los 3 modos de ejecución.

```bash
python3 test_execution_modes.py
```

Verifica:
- Command validator
- Database migration
- LLM execution state
- MCP tools registration

## Documentación Detallada

### `LLM_EXECUTION_MODES.md`
Documentación exhaustiva de los 3 modos de ejecución LLM.

Incluye:
- Comparación detallada
- Flujos de ejecución
- Ejemplos de código
- Casos de uso
- Troubleshooting

**Para usuarios normales**: Ver `docs/USO_RAPIDO.md` en su lugar.

**Para desarrolladores/integración LLM**: Este archivo tiene todos los detalles técnicos.

### Otros documentos (legacy)

- `LLM_INTEGRATION_ANALYSIS.md` - Análisis original de integración
- `AUTO_TOOL_INSTALLATION.md` - Docs de auto-instalación
- `CLEANUP_SCRIPTS.md` - Docs de limpieza
- `RESUMEN_EJECUTIVO.md` - Resumen ejecutivo inicial
- `UPGRADE_TO_v0.2.0.md` - Upgrade v0.2.0

Estos son documentos históricos del proceso de desarrollo.

## Cuándo Usar

### Use estos scripts si:

1. **Error MCP**
   - Connection closed
   - Error -32000
   → Ejecuta `migrate_database.py`

2. **SSL no funciona**
   - Services SSL usan HTTP en vez de HTTPS
   → Ejecuta `test_ssl_detection.py` para verificar
   → Si falla, reinstala con `pip install -e . --force-reinstall`

3. **Desarrollando nuevas features**
   - Ejecuta `verify_installation.py` después de cambios
   - Ejecuta tests específicos según lo que modifiques

4. **Debugging**
   - `verify_installation.py` muestra estado completo
   - Tests individuales para componentes específicos

### NO uses estos scripts para:

- ❌ Uso normal del sistema (usa MCP tools desde Cursor)
- ❌ Gestión de proyectos (usa `scripts/` en lugar)
- ❌ Limpieza rutinaria (usa `scripts/delete_project_completely.py`)

## Estructura

```
dev-tools/
├── README.md (este archivo)
│
├── Verificación
│   ├── verify_installation.py
│   └── migrate_database.py
│
├── Testing
│   ├── test_ssl_detection.py
│   ├── test_nmap_parser_ssl.py
│   ├── test_nmap_formats.py
│   └── test_execution_modes.py
│
└── Documentación Detallada
    ├── LLM_EXECUTION_MODES.md
    ├── LLM_INTEGRATION_ANALYSIS.md
    ├── AUTO_TOOL_INSTALLATION.md
    ├── CLEANUP_SCRIPTS.md
    ├── RESUMEN_EJECUTIVO.md
    └── UPGRADE_TO_v0.2.0.md
```

## Mantenimiento

Estos scripts deben:
- ✅ Mantenerse actualizados con el código
- ✅ Ejecutarse sin errores en cada release
- ✅ Documentarse claramente
- ✅ Estar aislados del código de producción

## Para Contribuidores

Si añades una nueva feature:

1. Añade test en `dev-tools/test_*.py`
2. Actualiza `verify_installation.py` si aplica
3. Documenta en `LLM_EXECUTION_MODES.md` si es modo LLM
4. Ejecuta todos los tests antes de PR

---

**Nota**: Para uso normal del sistema, consulta la documentación principal en `docs/`.
