# ✅ Configuración del Puerto Kali - Completada

## Problema Resuelto

El puerto del servidor Kali MCP estaba hardcodeado en `5001`. **Ahora es completamente configurable**.

---

## 🎯 Solución Implementada

### 1. **Variable de Entorno** (Método Recomendado)

```bash
export KALI_SERVER_URL="http://127.0.0.1:8080"
```

### 2. **Argumento de Línea de Comandos**

```bash
python3 -m audit_orchestrator.mcp_server \
  --kali-server-url "http://kali-server:5001"
```

### 3. **Configuración en mcp_servers.json**

```json
{
  "mcpServers": {
    "audit-orchestrator": {
      "command": "python3",
      "args": [
        "-m", "audit_orchestrator.mcp_server",
        "--kali-server-url", "http://192.168.1.100:5001"
      ]
    }
  }
}
```

### 4. **Script Interactivo** (Nuevo)

```bash
./scripts/configure-kali-port.sh 8080
```

---

## 📚 Documentación Creada

### Archivos Nuevos

1. **`docs/CONFIGURACION.md`** (400+ líneas)
   - Guía completa de todas las variables de entorno
   - Ejemplos para Docker, remoto, proxy, load balancing
   - Troubleshooting detallado
   - Valores recomendados por entorno

2. **`CONFIGURAR_PUERTO_KALI.md`**
   - Guía rápida con ejemplos directos
   - 3 ejemplos completos
   - Verificación de configuración
   - Troubleshooting común

3. **`scripts/configure-kali-port.sh`**
   - Script interactivo bash
   - Prueba conexión automáticamente
   - Configuración permanente opcional

### Archivos Actualizados

1. **`README.md`**
   - Link a `CONFIGURACION.md` en sección de documentación
   - Ejemplo actualizado en mcp_servers.json con puerto configurable
   - Nota sobre configuración del puerto

2. **`QUICK_START.md`**
   - Nueva sección "Configure Kali Server URL"
   - Ejemplo actualizado con `--kali-server-url`
   - Link a guía de configuración

3. **`docs/CHANGELOG.md`**
   - Documentado en v0.3.0
   - Sección de documentación de configuración

---

## 🔧 Código Existente

**El código ya soportaba configuración** desde antes:

### `config.py` (línea 31-34)
```python
self.kali_server_url = kali_server_url or os.environ.get(
    "KALI_SERVER_URL", 
    "http://127.0.0.1:5001"
)
```

### `mcp_server/__init__.py` (línea 1075-1077)
```python
"--kali-server-url",
help="MCP Kali server URL (default: http://127.0.0.1:5001)"
```

### `kali_client.py` (línea 23)
```python
def __init__(self, server_url: str = "http://127.0.0.1:5001", timeout: int = 900):
```

**Todas las partes del código ya usaban `settings.kali_server_url`** ✅

---

## 📋 Ejemplos de Uso

### Ejemplo 1: Puerto Local Diferente

```bash
# Servidor Kali en puerto 8080
export KALI_SERVER_URL="http://127.0.0.1:8080"

# Verificar
echo $KALI_SERVER_URL
# Output: http://127.0.0.1:8080

# Iniciar orchestrator
python3 -m audit_orchestrator.mcp_server
```

### Ejemplo 2: Servidor Remoto

```bash
export KALI_SERVER_URL="http://kali.redteam.local:5001"
python3 -m audit_orchestrator.mcp_server
```

### Ejemplo 3: Con Script Interactivo

```bash
cd /opt/cline-mcps/MVP-audit-orchestrator
./scripts/configure-kali-port.sh 8080

# Output:
# ╔═══════════════════════════════════════════════════════════╗
# ║   Configurador de Puerto Kali MCP - Audit Orchestrator   ║
# ╚═══════════════════════════════════════════════════════════╝
# 
# Nueva configuración:
#   Host: 127.0.0.1
#   Puerto: 8080
#   URL completa: http://127.0.0.1:8080
# 
# Probando conexión...
# ✅ Servidor Kali MCP responde correctamente
```

### Ejemplo 4: En Cursor mcp_servers.json

```json
{
  "mcpServers": {
    "audit-orchestrator": {
      "command": "python3",
      "args": [
        "-m", "audit_orchestrator.mcp_server",
        "--transport", "stdio",
        "--kali-server-url", "http://10.0.0.50:5001"
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

---

## ✅ Verificación

### Test 1: Ver Configuración Actual

```bash
python3 << 'EOF'
from audit_orchestrator.config import Settings
settings = Settings.from_args()
print(f"Kali Server URL: {settings.kali_server_url}")
print(f"Max Concurrent: {settings.max_concurrent_targets}")
print(f"Auto Review: {settings.auto_review_on_run}")
EOF
```

### Test 2: Probar Conexión

```bash
# Con curl
curl http://127.0.0.1:5001/health

# Con Python
python3 << 'EOF'
import asyncio
from audit_orchestrator.core.kali_client import test_kali_connection

async def test():
    result = await test_kali_connection("http://127.0.0.1:5001")
    print(f"✅ Connected: {result}")

asyncio.run(test())
EOF
```

---

## 🎓 Variables de Entorno Disponibles

| Variable | Default | Descripción |
|----------|---------|-------------|
| `KALI_SERVER_URL` | `http://127.0.0.1:5001` | URL del servidor Kali MCP |
| `AUDIT_MAX_CONCURRENT` | `10` | Max targets simultáneos |
| `AUDIT_AUTO_REVIEW` | `true` | Auto-review antes de run |
| `AUDIT_ERROR_THRESHOLD` | `0.8` | Threshold de error (80%) |

---

## 📖 Documentación Completa

Para más información, consultar:

1. **`docs/CONFIGURACION.md`** - Guía completa de configuración
2. **`CONFIGURAR_PUERTO_KALI.md`** - Guía rápida de puerto
3. **`README.md`** - Inicio rápido actualizado
4. **`QUICK_START.md`** - Guía paso a paso
5. **`docs/CHANGELOG.md`** - Historial de cambios

---

## ✨ Resumen

✅ **Puerto del servidor Kali completamente configurable**  
✅ **3 métodos de configuración disponibles**  
✅ **Script interactivo para facilitar configuración**  
✅ **Documentación completa con ejemplos**  
✅ **Código ya soportaba configuración (solo faltaba documentación)**  

**Versión**: 0.3.0  
**Fecha**: 2026-10-02
