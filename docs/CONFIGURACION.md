# Configuración del Audit Orchestrator

## Variables de Entorno

### Servidor Kali MCP

**Variable**: `KALI_SERVER_URL`  
**Default**: `http://127.0.0.1:5001`  
**Descripción**: URL completa del servidor Kali MCP (incluyendo protocolo, host y puerto)

#### Ejemplos de Configuración

**1. Puerto diferente en localhost:**
```bash
export KALI_SERVER_URL="http://127.0.0.1:8080"
```

**2. Servidor remoto:**
```bash
export KALI_SERVER_URL="http://kali-server.local:5001"
```

**3. Con HTTPS:**
```bash
export KALI_SERVER_URL="https://kali.empresa.com:443"
```

**4. IP específica:**
```bash
export KALI_SERVER_URL="http://192.168.1.100:5001"
```

### Configuración de Ejecución Paralela

**Variable**: `AUDIT_MAX_CONCURRENT`  
**Default**: `10`  
**Descripción**: Número máximo de targets a auditar simultáneamente

```bash
export AUDIT_MAX_CONCURRENT=15
```

**Variable**: `AUDIT_AUTO_REVIEW`  
**Default**: `true`  
**Descripción**: Ejecutar auto-review antes de auditar (detecta y re-encola fallos)

```bash
export AUDIT_AUTO_REVIEW=false  # Deshabilitar auto-review
```

**Variable**: `AUDIT_ERROR_THRESHOLD`  
**Default**: `0.8` (80%)  
**Descripción**: Umbral de error para detectar auditorías fallidas

```bash
export AUDIT_ERROR_THRESHOLD=0.6  # Más estricto (60%)
```

---

## Configuración por Línea de Comandos

### Al iniciar el servidor MCP

```bash
python3 -m audit_orchestrator.mcp_server \
  --kali-server-url "http://192.168.1.100:8080" \
  --data-dir "/custom/path/data"
```

### Argumentos disponibles

```
--kali-server-url URL    URL del servidor Kali MCP (default: http://127.0.0.1:5001)
--data-dir PATH          Directorio para base de datos (default: ~/.local/share/audit-orchestrator)
--transport TRANSPORT    Transporte MCP: stdio o sse (default: stdio)
```

---

## Configuración Permanente

### Opción 1: Variables de entorno globales

**Linux/macOS** - Añadir a `~/.bashrc` o `~/.zshrc`:

```bash
# Configuración Audit Orchestrator
export KALI_SERVER_URL="http://kali-server:5001"
export AUDIT_MAX_CONCURRENT=15
export AUDIT_AUTO_REVIEW=true
export AUDIT_ERROR_THRESHOLD=0.8
```

Luego:
```bash
source ~/.bashrc
```

### Opción 2: Archivo .env en el proyecto

Crear `/opt/cline-mcps/MVP-audit-orchestrator/.env`:

```bash
KALI_SERVER_URL=http://192.168.1.100:5001
AUDIT_MAX_CONCURRENT=10
AUDIT_AUTO_REVIEW=true
AUDIT_ERROR_THRESHOLD=0.8
```

Cargar antes de ejecutar:
```bash
export $(cat .env | xargs)
python3 -m audit_orchestrator.mcp_server
```

### Opción 3: Configurar en MCP servers.json de Cursor

Editar `~/.cursor/mcp_servers.json`:

```json
{
  "mcpServers": {
    "audit-orchestrator": {
      "command": "python3",
      "args": [
        "-m", "audit_orchestrator.mcp_server",
        "--kali-server-url", "http://kali-server:5001",
        "--data-dir", "/custom/data/path"
      ],
      "env": {
        "AUDIT_MAX_CONCURRENT": "15",
        "AUDIT_AUTO_REVIEW": "true",
        "AUDIT_ERROR_THRESHOLD": "0.8"
      },
      "cwd": "/opt/cline-mcps/MVP-audit-orchestrator"
    }
  }
}
```

---

## Verificar Configuración Actual

### Método 1: Desde Python

```python
from audit_orchestrator.config import Settings

settings = Settings.from_args()

print(f"Kali Server URL: {settings.kali_server_url}")
print(f"Max Concurrent: {settings.max_concurrent_targets}")
print(f"Auto Review: {settings.auto_review_on_run}")
print(f"Error Threshold: {settings.review_error_threshold}")
print(f"Data Dir: {settings.data_dir}")
```

### Método 2: Verificar variables de entorno

```bash
echo "KALI_SERVER_URL: ${KALI_SERVER_URL:-http://127.0.0.1:5001}"
echo "AUDIT_MAX_CONCURRENT: ${AUDIT_MAX_CONCURRENT:-10}"
echo "AUDIT_AUTO_REVIEW: ${AUDIT_AUTO_REVIEW:-true}"
echo "AUDIT_ERROR_THRESHOLD: ${AUDIT_ERROR_THRESHOLD:-0.8}"
```

---

## Test de Conexión con Servidor Kali

### Script de test rápido

```bash
python3 << 'EOF'
import asyncio
import os
from audit_orchestrator.core.kali_client import test_kali_connection

async def test():
    url = os.environ.get("KALI_SERVER_URL", "http://127.0.0.1:5001")
    print(f"🔍 Testing connection to: {url}")
    
    try:
        result = await test_kali_connection(url)
        print(f"✅ Connection successful!")
        print(f"   Version: {result.get('version', 'unknown')}")
        print(f"   Status: {result.get('status', 'unknown')}")
    except Exception as e:
        print(f"❌ Connection failed: {e}")

asyncio.run(test())
EOF
```

---

## Escenarios Comunes

### Escenario 1: Kali Server en Docker

```bash
# Kali MCP corriendo en Docker con puerto mapeado
docker run -d -p 8080:5001 kali-mcp-server

# Configurar orchestrator
export KALI_SERVER_URL="http://127.0.0.1:8080"
```

### Escenario 2: Kali Server Remoto

```bash
# Servidor Kali dedicado en la red
export KALI_SERVER_URL="http://10.0.0.50:5001"

# Con autenticación (si el servidor la requiere en el futuro)
export KALI_SERVER_URL="http://user:pass@10.0.0.50:5001"
```

### Escenario 3: Múltiples Entornos

**Producción** (`~/.bashrc`):
```bash
export KALI_SERVER_URL="http://kali-prod.empresa.com:5001"
export AUDIT_MAX_CONCURRENT=20
```

**Desarrollo** (script local):
```bash
#!/bin/bash
export KALI_SERVER_URL="http://localhost:5001"
export AUDIT_MAX_CONCURRENT=5
python3 -m audit_orchestrator.mcp_server
```

**Testing** (script de test):
```bash
#!/bin/bash
export KALI_SERVER_URL="http://kali-test:5001"
export AUDIT_MAX_CONCURRENT=2
export AUDIT_AUTO_REVIEW=false  # Deshabilitar para tests
python3 -m audit_orchestrator.mcp_server
```

---

## Troubleshooting

### Error: "Could not connect to MCP Kali server"

**1. Verificar que el servidor Kali MCP está corriendo:**
```bash
curl -X POST http://127.0.0.1:5001/health
```

**2. Verificar la URL configurada:**
```bash
echo $KALI_SERVER_URL
```

**3. Probar conexión con timeout corto:**
```bash
curl -m 5 http://127.0.0.1:5001/health || echo "❌ No responde"
```

**4. Verificar firewall/red:**
```bash
# Ping al host
ping -c 3 kali-server

# Verificar puerto abierto
nc -zv kali-server 5001
# o
telnet kali-server 5001
```

### Error: "Connection refused"

**Causa común**: Puerto incorrecto o servidor no iniciado

**Solución**:
```bash
# 1. Verificar qué está usando el puerto 5001
sudo lsof -i :5001

# 2. Si no hay nada, iniciar el servidor Kali MCP
python3 -m kali_mcp_server --port 5001

# 3. Si quieres usar otro puerto
python3 -m kali_mcp_server --port 8080
export KALI_SERVER_URL="http://127.0.0.1:8080"
```

### Error: "Timeout"

**Causa**: Red lenta o comandos muy largos

**Solución**: Ajustar timeout (no recomendado cambiar default 900s):
```python
# En código personalizado
from audit_orchestrator.core.kali_client import KaliMCPClient

client = KaliMCPClient(
    server_url="http://kali-server:5001",
    timeout=1800  # 30 minutos
)
```

---

## Configuración Avanzada

### Proxy HTTP

Si necesitas acceder al servidor Kali a través de un proxy:

```bash
export HTTP_PROXY="http://proxy.empresa.com:8080"
export HTTPS_PROXY="http://proxy.empresa.com:8080"
export KALI_SERVER_URL="http://kali-server:5001"
```

### Múltiples Servidores Kali (Load Balancing)

Para distribuir carga entre varios servidores Kali (requiere nginx o similar):

```nginx
# nginx.conf
upstream kali_backend {
    least_conn;
    server kali1.local:5001;
    server kali2.local:5001;
    server kali3.local:5001;
}

server {
    listen 5001;
    location / {
        proxy_pass http://kali_backend;
    }
}
```

```bash
export KALI_SERVER_URL="http://nginx-loadbalancer:5001"
```

---

## Valores Recomendados

| Entorno | Max Concurrent | Auto Review | Error Threshold | Notas |
|---------|----------------|-------------|-----------------|-------|
| **Laptop local** | 5-10 | true | 0.8 | Recursos limitados |
| **Workstation** | 15-25 | true | 0.8 | CPU/RAM abundantes |
| **Servidor dedicado** | 30-50 | true | 0.7 | Máxima paralelización |
| **Producción** | 20 | true | 0.8 | Balance rendimiento/estabilidad |
| **Testing/Debug** | 2-5 | false | 0.9 | Control fino |

---

**Última actualización**: 2026-10-02  
**Versión**: 0.3.0
