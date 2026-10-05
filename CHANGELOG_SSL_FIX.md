# Fix: Detección SSL/HTTP para auditorías default_blackbox

## Problema identificado

En la auditoría del target `10.19.220.6`, el puerto 80 (HTTP puro) era incorrectamente detectado como HTTPS, causando:

- Ejecución innecesaria de herramientas SSL (`sslscan`, `testssl.sh`, `ssl-cert`)
- Uso incorrecto del esquema `https://` en todas las URLs para puerto 80
- Fallos en handshakes SSL y comandos timeout

### Causa raíz

```bash
# Comando antiguo de detección SSL
timeout 5 openssl s_client -connect {target}:{port} < /dev/null 2>&1 | grep -q 'Cipher'
```

Este comando producía **falsos positivos** porque encontraba la palabra "Cipher" incluso cuando el resultado era:
```
New, (NONE), Cipher is (NONE)  # ← Puerto HTTP puro, NO SSL
```

## Solución implementada

### 1. Detección SSL robusta y en tres niveles

Se mejoró `_detect_ssl_on_port()` en `orchestrator.py` con la siguiente estrategia:

#### Nivel 1: Análisis de nombre de servicio (nmap -sV)
```python
# Indicadores SSL explícitos
if any(indicator in service_lower for indicator in ["https", "ssl", "tls", "imaps", "pop3s", "smtps", "ftps"]):
    return True  # ✓ SSL detectado via nombre de servicio

# Servicios explícitamente NO-SSL
if service_lower in ["http", "ftp", "smtp", "pop3", "imap", "telnet"]:
    return False  # ✗ Servicio HTTP/plain text
```

#### Nivel 2: Puertos conocidos
```python
# Puertos estándar
if port == 443:      return True   # ✓ HTTPS
if port == 80:       return False  # ✗ HTTP
if port in [8443, 9443, 10443]:  return True   # ✓ HTTPS alternos
if port in [8080, 8000, 8008]:   return False  # ✗ HTTP alternos
```

#### Nivel 3: Test con openssl (puertos desconocidos)
```bash
# Comando mejorado: busca cipher real, NO "(NONE)"
timeout 5 openssl s_client -connect {target}:{port} < /dev/null 2>&1 | grep 'Cipher' | grep -qv '(NONE)'
```

### 2. Flujo programático correcto

```
1. all_services: nmap -sV, nmap -sC  → Detecta servicio y versión
                      ↓
2. _detect_ssl_on_port()              → Determina HTTP vs HTTPS
                      ↓
3. Selección de perfil:
   - Si HTTP  → tasks["http"]  (sin SSL tools, http://)
   - Si HTTPS → tasks["https"] (con SSL tools, https://)
```

## Validación

### Tests unitarios (13/13 ✅)
- ✅ Detección SSL por nombre de servicio (`https`, `ssl/radan-http`)
- ✅ Detección no-SSL por nombre de servicio (`http`)
- ✅ Puerto 80 → HTTP
- ✅ Puerto 443 → HTTPS
- ✅ Puertos comunes HTTP/HTTPS (8080, 8443, etc.)
- ✅ Test con openssl (con/sin SSL real)
- ✅ Manejo de errores

### Tests de integración contra 10.19.220.6 (3/3 ✅)
- ✅ Puerto 80 (http) → NO SSL detectado
- ✅ Puerto 443 (https) → SSL detectado correctamente
- ✅ Puerto 22 (ssh) → NO tratado como web SSL

### Archivos modificados
- `src/audit_orchestrator/core/orchestrator.py` - Función `_detect_ssl_on_port()` reescrita
- `tests/test_ssl_detection.py` - Tests unitarios exhaustivos
- `tests/test_ssl_integration_10_19_220_6.py` - Tests de integración real

## Resultados esperados

### Antes (INCORRECTO ❌)
```
[2026-10-05 09:41:57] SERVICE: 80/tcp (http)
[2026-10-05 09:41:57] ✓ SSL/TLS detected - using HTTPS  ← FALSO POSITIVO
[2026-10-05 09:42:16] TASK: ssl_scan
[2026-10-05 09:42:16] COMMAND: /usr/bin/sslscan 10.19.220.6:80  ← INNECESARIO
[2026-10-05 09:42:20] COMMAND: /usr/bin/whatweb https://10.19.220.6:80  ← ESQUEMA INCORRECTO
```

### Después (CORRECTO ✅)
```
[2026-10-05 XX:XX:XX] SERVICE: 80/tcp (http)
[2026-10-05 XX:XX:XX] ✗ Non-SSL service 'http' detected - using HTTP  ← CORRECTO
[2026-10-05 XX:XX:XX] TASK: whatweb
[2026-10-05 XX:XX:XX] COMMAND: /usr/bin/whatweb http://10.19.220.6:80  ← HTTP CORRECTO
# No se ejecutan sslscan, testssl.sh, ni ssl-cert en puerto 80
```

## Próximos pasos

- ✅ Tests pasan
- ⏳ Validar con auditoría completa en target 10.19.220.6
- ⏳ Verificar outputs en `/home/f0ns1/RedTeam/OCSR25/infra/Audit/10.19.220.6/enumeration/`
- ⏳ Confirmar que puerto 443 usa correctamente perfil HTTPS

## Fecha
2026-10-05 10:XX UTC+2
