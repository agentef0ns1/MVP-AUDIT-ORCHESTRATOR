# Configurar Puerto del Servidor Kali MCP

## 🎯 Resumen Rápido

El puerto del servidor Kali MCP (default: `5001`) es **completamente configurable**.

### Opción 1: Variable de Entorno (Recomendado)

```bash
export KALI_SERVER_URL="http://127.0.0.1:8080"
```

### Opción 2: Argumento de Línea de Comandos

```bash
python3 -m audit_orchestrator.mcp_server \
  --kali-server-url "http://192.168.1.100:8080"
```

### Opción 3: En mcp_servers.json de Cursor

```json
{
  "mcpServers": {
    "audit-orchestrator": {
      "command": "python3",
      "args": [
        "-m", "audit_orchestrator.mcp_server",
        "--kali-server-url", "http://kali-server:8080"
      ],
      "cwd": "/opt/cline-mcps/MVP-audit-orchestrator"
    }
  }
}
```

---

## 📖 Ejemplos Completos

### Ejemplo 1: Puerto 8080 en localhost

```bash
# Terminal 1: Servidor Kali MCP en puerto 8080
python3 -m kali_mcp_server --port 8080

# Terminal 2: Audit Orchestrator configurado
export KALI_SERVER_URL="http://127.0.0.1:8080"
python3 -m audit_orchestrator.mcp_server
```

### Ejemplo 2: Servidor remoto

```bash
export KALI_SERVER_URL="http://kali.empresa.com:5001"
python3 -m audit_orchestrator.mcp_server
```

### Ejemplo 3: Docker con puerto mapeado

```bash
# Kali MCP en Docker con puerto 9000 → 5001
docker run -d -p 9000:5001 kali-mcp-server

# Configurar orchestrator
export KALI_SERVER_URL="http://127.0.0.1:9000"
```

---

## ✅ Verificar Configuración

```bash
# Ver configuración actual
python3 << 'EOF'
from audit_orchestrator.config import Settings
settings = Settings.from_args()
print(f"Kali Server URL: {settings.kali_server_url}")
EOF
```

**Salida esperada:**
```
Kali Server URL: http://127.0.0.1:5001
```

---

## 🔧 Configuración Permanente

**Linux/macOS** - Añadir a `~/.bashrc`:

```bash
# Configuración Audit Orchestrator
export KALI_SERVER_URL="http://kali-server:8080"
```

Luego:
```bash
source ~/.bashrc
```

---

## 🚨 Troubleshooting

### Error: "Could not connect to MCP Kali server"

**1. Verificar que el servidor está corriendo:**
```bash
curl http://127.0.0.1:5001/health
```

**2. Verificar la URL configurada:**
```bash
echo $KALI_SERVER_URL
```

**3. Probar otro puerto:**
```bash
export KALI_SERVER_URL="http://127.0.0.1:8080"
```

---

## 📚 Documentación Completa

Ver [docs/CONFIGURACION.md](docs/CONFIGURACION.md) para:
- Todas las variables de entorno
- Configuración avanzada
- Múltiples entornos
- Proxy y load balancing
- Y mucho más

---

**Versión**: 0.3.0  
**Última actualización**: 2026-10-02
